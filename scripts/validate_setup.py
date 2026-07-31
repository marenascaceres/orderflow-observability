#!/usr/bin/env python3
"""
OrderFlow - Validador del setup
================================
Ejecuta health-checks contra los 10 servicios del stack y reporta
estado en forma de tabla. Uso:

    python scripts/validate_setup.py

Si algo falla, imprime el diagnostico y termina con exit code 1.
Solo depende de la stdlib de Python 3.8+.
"""

import json
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Callable

RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"


def check_http(url: str, timeout: float = 5.0, expect_status: int = 200, contains: str | None = None) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "orderflow-validator"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            body = resp.read(4096).decode("utf-8", errors="ignore")
            if status != expect_status:
                return False, f"HTTP {status} (esperaba {expect_status})"
            if contains and contains not in body:
                return False, f"body no contiene '{contains}'"
            return True, f"HTTP {status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def check_docker_exec(container: str, cmd: list[str], expect_in_output: str) -> tuple[bool, str]:
    full = ["docker", "compose", "exec", "-T", container] + cmd
    try:
        result = subprocess.run(full, capture_output=True, text=True, timeout=10)
        out = (result.stdout + result.stderr).strip()
        if expect_in_output.lower() in out.lower():
            return True, out.splitlines()[-1] if out else "ok"
        return False, out[:120] if out else "sin salida"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except FileNotFoundError:
        return False, "docker no disponible en PATH"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def check_prometheus_target(job: str) -> tuple[bool, str]:
    try:
        req = urllib.request.Request("http://localhost:9090/api/v1/targets", headers={"User-Agent": "validator"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for t in data.get("data", {}).get("activeTargets", []):
            if t.get("labels", {}).get("job") == job:
                if t.get("health") == "up":
                    return True, "UP"
                return False, f"health={t.get('health')}"
        return False, f"target '{job}' no encontrado"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def check_elasticsearch_index() -> tuple[bool, str]:
    try:
        req = urllib.request.Request("http://localhost:9200/_cat/indices?format=json", headers={"User-Agent": "validator"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            indices = json.loads(resp.read().decode("utf-8"))
        matches = [i for i in indices if i.get("index", "").startswith("orderflow-logs-")]
        if matches:
            total_docs = sum(int(i.get("docs.count", 0) or 0) for i in matches)
            return True, f"{len(matches)} indice(s), {total_docs} docs"
        return False, "sin indices orderflow-logs-* (esperar 30s tras arranque)"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


CHECKS: list[tuple[str, Callable[[], tuple[bool, str]]]] = [
    ("Prometheus UI",           lambda: check_http("http://localhost:9090/-/ready")),
    ("Prometheus target: generator",  lambda: check_prometheus_target("order-generator")),
    ("Prometheus target: processor",  lambda: check_prometheus_target("order-processor")),
    ("Alertmanager UI",         lambda: check_http("http://localhost:9093/-/ready")),
    ("Grafana UI",              lambda: check_http("http://localhost:3000/api/health", contains="ok")),
    ("Elasticsearch cluster",   lambda: check_http("http://localhost:9200/_cluster/health", contains="cluster_name")),
    ("Elasticsearch: indice orderflow-logs-*", lambda: check_elasticsearch_index()),
    ("Kibana UI",               lambda: check_http("http://localhost:5601/api/status", contains="status")),
    ("order-generator /metrics", lambda: check_http("http://localhost:8000/metrics", contains="orderflow_orders_generated_total")),
    ("order-processor /metrics", lambda: check_http("http://localhost:8001/metrics", contains="orderflow_orders_processed_total")),
    ("Postgres accepting connections", lambda: check_docker_exec("postgres", ["pg_isready", "-U", "orderflow"], "accepting connections")),
    ("Redis PING",              lambda: check_docker_exec("redis", ["redis-cli", "ping"], "PONG")),
]


def main() -> int:
    print(f"{BOLD}OrderFlow - Validador del setup{RESET}\n")
    print(f"{'Check':<48} {'Estado':<10} Detalle")
    print("-" * 90)

    failed = 0
    for name, check in CHECKS:
        try:
            ok, detail = check()
        except Exception as e:
            ok, detail = False, f"excepcion: {e}"

        status = f"{GREEN}OK{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"{name:<48} {status:<19} {detail}")
        if not ok:
            failed += 1

    print("-" * 90)
    total = len(CHECKS)
    passed = total - failed

    if failed == 0:
        print(f"\n{GREEN}{BOLD}Todos los checks OK ({passed}/{total}){RESET}")
        print("El stack esta funcional. Puedes continuar con la practica exploratoria.\n")
        return 0
    else:
        print(f"\n{RED}{BOLD}{failed} check(s) fallaron ({passed}/{total} OK){RESET}")
        print(f"\n{YELLOW}Sugerencias:{RESET}")
        print("  1. Espera 30-60s adicionales: Elasticsearch y Kibana arrancan lento.")
        print("  2. Verifica estado de servicios:  docker compose ps")
        print("  3. Revisa logs del servicio que falla:  docker compose logs <servicio>")
        print("  4. Consulta docs/troubleshooting.md")
        return 1


if __name__ == "__main__":
    sys.exit(main())
