#!/usr/bin/env python3
"""
OrderFlow - Validador de la Sesion 2
=====================================
Comprueba que el stack quedo correctamente ampliado tras la Sesion 2:
exporters, Pushgateway, los 6 targets de Prometheus y la metrica que
instrumentaste tu.

    python scripts/validate_sesion2.py

Solo depende de la stdlib de Python 3.8+.
"""

import json
import sys
import urllib.error
import urllib.request

RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"

TARGETS_ESPERADOS = [
    "prometheus",
    "order-generator",
    "order-processor",
    "postgres-exporter",
    "redis-exporter",
    "pushgateway",
]


def get(url: str, timeout: float = 5.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "orderflow-validator"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def check_metrics_endpoint(url: str, expected: str):
    """El endpoint /metrics responde y contiene la metrica indicada."""
    try:
        body = get(url)
    except Exception as e:
        return False, f"{type(e).__name__}: no responde"
    if expected not in body:
        return False, f"responde pero no expone '{expected}'"
    return True, "OK"


def check_pushgateway():
    try:
        get("http://localhost:9091/-/healthy")
        return True, "OK"
    except Exception as e:
        return False, f"{type(e).__name__}: no responde"


def check_targets():
    """Los 6 targets esperados existen y estan UP."""
    try:
        data = json.loads(get("http://localhost:9090/api/v1/targets"))
    except Exception as e:
        return False, f"Prometheus no responde ({type(e).__name__})"

    activos = data.get("data", {}).get("activeTargets", [])
    estado = {t.get("labels", {}).get("job"): t.get("health") for t in activos}

    faltan = [j for j in TARGETS_ESPERADOS if j not in estado]
    if faltan:
        return False, f"faltan targets: {', '.join(faltan)} (recarga Prometheus)"

    caidos = [j for j in TARGETS_ESPERADOS if estado.get(j) != "up"]
    if caidos:
        return False, f"targets caidos: {', '.join(caidos)}"

    return True, f"{len(TARGETS_ESPERADOS)}/6 UP"


def check_etiquetas_scrape():
    """Las etiquetas service/component siguen presentes.

    Si alguien reemplaza prometheus.yml en vez de ampliarlo, estas
    etiquetas desaparecen y las consultas 'sum by (service)' dejan de
    funcionar sin dar ningun error visible.
    """
    try:
        data = json.loads(get("http://localhost:9090/api/v1/targets"))
    except Exception as e:
        return False, f"Prometheus no responde ({type(e).__name__})"

    for t in data.get("data", {}).get("activeTargets", []):
        labels = t.get("labels", {})
        if labels.get("job") == "order-processor":
            if labels.get("service") == "processor" and labels.get("component") == "pipeline":
                return True, "service/component presentes"
            return False, "faltan las etiquetas service/component en order-processor"
    return False, "target order-processor no encontrado"


def check_alertmanager_configurado():
    """Prometheus conoce a Alertmanager.

    No hace falta hasta la Sesion 5, pero si se pierde ahora nadie se
    entera hasta entonces, y para ese momento cuesta mucho diagnosticar.
    """
    try:
        data = json.loads(get("http://localhost:9090/api/v1/alertmanagers"))
    except Exception as e:
        return False, f"Prometheus no responde ({type(e).__name__})"

    activos = data.get("data", {}).get("activeAlertmanagers", [])
    if activos:
        return True, f"{len(activos)} alertmanager(s)"
    return False, "Prometheus no conoce ningun Alertmanager (revisa el bloque alerting: de prometheus.yml)"


def check_metrica_del_alumno():
    """Ejercicio del Bloque 4. Opcional: no invalida la sesion."""
    try:
        body = get("http://localhost:8001/metrics")
    except Exception as e:
        return False, f"{type(e).__name__}: order-processor no responde"
    if "orderflow_order_amount_soles_total" in body:
        return True, "instrumentada correctamente"
    return False, "aun no instrumentada (Bloque 4 del manual)"


CHECKS = [
    ("postgres-exporter publica metricas", lambda: check_metrics_endpoint("http://localhost:9187/metrics", "pg_up"), True),
    ("redis-exporter publica metricas", lambda: check_metrics_endpoint("http://localhost:9121/metrics", "redis_up"), True),
    ("pushgateway responde", check_pushgateway, True),
    ("Prometheus scrapea los 6 targets", check_targets, True),
    ("Etiquetas service/component conservadas", check_etiquetas_scrape, True),
    ("Prometheus conoce a Alertmanager", check_alertmanager_configurado, True),
    ("Tu metrica orderflow_order_amount_soles_total", check_metrica_del_alumno, False),
]


def main() -> int:
    print(f"{BOLD}OrderFlow - Validador de la Sesion 2{RESET}\n")
    print(f"{'Check':<48} {'Estado':<10} Detalle")
    print("-" * 92)

    fallos_criticos = 0
    avisos = 0

    for nombre, check, obligatorio in CHECKS:
        try:
            ok, detalle = check()
        except Exception as e:
            ok, detalle = False, f"excepcion: {e}"

        if ok:
            estado = f"{GREEN}OK{RESET}"
        elif obligatorio:
            estado = f"{RED}FAIL{RESET}"
            fallos_criticos += 1
        else:
            estado = f"{YELLOW}PEND{RESET}"
            avisos += 1

        print(f"{nombre:<48} {estado:<19} {detalle}")

    print("-" * 92)

    if fallos_criticos == 0 and avisos == 0:
        print(f"\n{GREEN}{BOLD}Sesion 2 completa. Todo listo para la Sesion 3.{RESET}\n")
        return 0

    if fallos_criticos == 0:
        print(f"\n{GREEN}{BOLD}El stack de la Sesion 2 esta correcto.{RESET}")
        print(f"{YELLOW}Queda pendiente el ejercicio de instrumentacion (Bloque 4 del manual).{RESET}")
        print("Puedes completarlo en casa.\n")
        return 0

    print(f"\n{RED}{BOLD}{fallos_criticos} check(s) obligatorios fallaron.{RESET}")
    print(f"\n{YELLOW}Sugerencias:{RESET}")
    print("  1. Confirma que actualizaste el repo:   git log --oneline -1")
    print("  2. Confirma que tienes 13 servicios:    docker compose ps")
    print("  3. Recarga la configuracion:            docker compose restart prometheus")
    print("  4. Revisa el servicio que falla:        docker compose logs <servicio> --tail 20")
    print("  5. Consulta docs/troubleshooting.md\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
