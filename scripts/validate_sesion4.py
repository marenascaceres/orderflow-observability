#!/usr/bin/env python3
"""
OrderFlow - Validador de la Sesion 4
=====================================
Comprueba que Grafana dejo de estar vacio y, sobre todo, que el
dashboard vive como archivo en el repositorio y no solo dentro de
la base de datos interna de Grafana.

    python scripts/validate_sesion4.py

Solo depende de la stdlib de Python 3.8+.
"""

import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# ------------------------------------------------------------
# Color en consola.
# ------------------------------------------------------------
# Windows PowerShell 5.1 no interpreta secuencias ANSI a menos que se
# active el modo terminal virtual. Sin esto el alumno ve basura del
# tipo "<-[92m" en lugar de texto verde. Si no se puede activar (o la
# salida se esta redirigiendo a un archivo), se apaga el color y la
# tabla sigue siendo perfectamente legible.
# ------------------------------------------------------------
def _activar_color() -> bool:
    if not sys.stdout.isatty():
        return False
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        modo = ctypes.c_ulong()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(modo)):
            return False
        # 0x0004 = ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return bool(kernel32.SetConsoleMode(handle, modo.value | 0x0004))
    except Exception:
        return False


if _activar_color():
    RESET = "\033[0m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BOLD = "\033[1m"
else:
    RESET = GREEN = RED = YELLOW = BOLD = ""

GRAFANA = f"http://localhost:{os.getenv('GRAFANA_PORT', '3000')}"
PROMETHEUS = f"http://localhost:{os.getenv('PROMETHEUS_PORT', '9090')}"
USER = os.getenv("GRAFANA_ADMIN_USER", "admin")
PASSWORD = os.getenv("GRAFANA_ADMIN_PASSWORD", "admin")

REPO = Path(__file__).resolve().parent.parent
DASHBOARDS_DIR = REPO / "grafana" / "dashboards"
UID = "orderflow-overview"

# Nombres que aparecen en las expresiones y que hay que verificar contra
# Prometheus. Se buscan por prefijo: lo nuestro y lo de los exporters.
METRICA_RE = re.compile(r"\b((?:orderflow|pg|redis)_[a-z0-9_]+)\b")


def _get(url: str, auth: bool = False, timeout: float = 8.0):
    req = urllib.request.Request(url, headers={"User-Agent": "orderflow-validator"})
    if auth:
        token = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


# --------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------

def check_grafana():
    try:
        data = _get(f"{GRAFANA}/api/health")
    except Exception as e:
        return False, f"Grafana no responde ({type(e).__name__})"
    if data.get("database") != "ok":
        return False, f"base de datos interna en estado '{data.get('database')}'"
    return True, f"version {data.get('version', '?')}"


def check_datasource(uid: str, tipo: str):
    try:
        data = _get(f"{GRAFANA}/api/datasources/uid/{uid}", auth=True)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, f"no existe ningun datasource con uid '{uid}'"
        if e.code == 401:
            return False, "credenciales de Grafana incorrectas (GRAFANA_ADMIN_PASSWORD)"
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, f"Grafana no responde ({type(e).__name__})"
    if data.get("type") != tipo:
        return False, f"el uid '{uid}' apunta a un datasource de tipo '{data.get('type')}'"
    return True, data.get("url", "")


def _leer_dashboard():
    """Devuelve (ruta, json) del dashboard exportado, o (None, motivo)."""
    if not DASHBOARDS_DIR.is_dir():
        return None, "no existe la carpeta grafana/dashboards/"
    candidatos = sorted(DASHBOARDS_DIR.glob("*.json"))
    if not candidatos:
        return None, "no hay ningun .json en grafana/dashboards/ (Paso 13)"
    preferido = DASHBOARDS_DIR / "orderflow-overview.json"
    ruta = preferido if preferido in candidatos else candidatos[0]
    try:
        return ruta, json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return None, f"{ruta.name} no es JSON valido: linea {e.lineno}"


def check_archivo():
    ruta, data = _leer_dashboard()
    if ruta is None:
        return False, data
    if not isinstance(data, dict) or "panels" not in data:
        return False, f"{ruta.name} no parece un dashboard (falta 'panels')"
    return True, f"{ruta.name}, {len(data['panels'])} paneles"


def check_paneles():
    ruta, data = _leer_dashboard()
    if ruta is None:
        return False, data
    paneles = data.get("panels", [])
    if len(paneles) < 5:
        faltan = 5 - len(paneles)
        return False, f"solo {len(paneles)} paneles; faltan {faltan}"
    tipos = {p.get("type") for p in paneles}
    esperados = {"timeseries", "stat", "gauge"}
    ausentes = esperados - tipos
    if ausentes:
        return False, f"no hay ningun panel de tipo {', '.join(sorted(ausentes))}"
    return True, f"{len(paneles)} paneles, tipos: {', '.join(sorted(tipos))}"


def check_id_null():
    """El 'id' heredado de la instalacion local rompe el provisioning ajeno."""
    ruta, data = _leer_dashboard()
    if ruta is None:
        return False, data
    if data.get("id") is not None:
        return False, f'"id": {data.get("id")} en vez de null (Paso 14)'
    return True, '"id": null'


def check_provisionado():
    """El dashboard debe estar cargado DESDE ARCHIVO, no solo guardado a clics."""
    try:
        data = _get(f"{GRAFANA}/api/dashboards/uid/{UID}", auth=True)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, f"Grafana no tiene ningun dashboard con uid '{UID}'"
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, f"Grafana no responde ({type(e).__name__})"

    meta = data.get("meta", {})
    if not meta.get("provisioned"):
        return False, "existe, pero guardado a mano: no viene del archivo (Paso 15)"
    carpeta = meta.get("folderTitle", "General")
    return True, f"provisionado, carpeta '{carpeta}'"


def check_metricas_existen():
    """Cada metrica citada en el dashboard tiene que existir en Prometheus.

    Es el check que atrapa un nombre mal escrito antes de que el alumno
    se pase media clase mirando un panel vacio.
    """
    ruta, data = _leer_dashboard()
    if ruta is None:
        return False, data

    texto = json.dumps(data)
    citadas = set(METRICA_RE.findall(texto))
    if not citadas:
        return False, "el dashboard no consulta ninguna metrica conocida"

    try:
        resp = _get(f"{PROMETHEUS}/api/v1/label/__name__/values")
    except Exception as e:
        return False, f"Prometheus no responde ({type(e).__name__})"
    existentes = set(resp.get("data", []))

    faltan = sorted(citadas - existentes)
    if faltan:
        return False, f"no existen en Prometheus: {', '.join(faltan)}"
    return True, f"{len(citadas)} metricas, todas existen"


def check_metrica_propia():
    """Ejercicio C: el panel con la metrica instrumentada en la Sesion 2."""
    ruta, data = _leer_dashboard()
    if ruta is None:
        return None, data
    if "orderflow_order_amount_soles_total" in json.dumps(data):
        return True, "el dashboard usa tu metrica de la Sesion 2"
    return None, "aun sin panel para orderflow_order_amount_soles_total"


CHECKS = [
    ("Grafana responde", check_grafana),
    ("Datasource Prometheus con uid fijo", lambda: check_datasource("prometheus", "prometheus")),
    ("Datasource Elasticsearch con uid fijo", lambda: check_datasource("elasticsearch", "elasticsearch")),
    ("Dashboard exportado a archivo", check_archivo),
    ("El JSON trae los 5 paneles", check_paneles),
    ('El JSON tiene "id": null', check_id_null),
    ("Grafana lo carga desde el archivo", check_provisionado),
    ("Las metricas del dashboard existen", check_metricas_existen),
    ("Ejercicio C: tu metrica de la Sesion 2", check_metrica_propia),
]


def main() -> int:
    print(f"{BOLD}OrderFlow - Validador de la Sesion 4{RESET}\n")
    print(f"{'Check':<44} {'Estado':<10} Detalle")
    print("-" * 96)

    fallos = 0
    for nombre, check in CHECKS:
        try:
            ok, detalle = check()
        except Exception as e:
            ok, detalle = False, f"excepcion: {e}"

        if ok is None:
            estado = f"{YELLOW}PEND{RESET}"
        elif ok:
            estado = f"{GREEN}OK{RESET}"
        else:
            estado = f"{RED}FAIL{RESET}"
            fallos += 1

        print(f"{nombre:<44} {estado:<19} {detalle}")

    print("-" * 96)

    if fallos == 0:
        print(f"\n{GREEN}{BOLD}Sesion 4 completa. Grafana ya no esta vacio.{RESET}")
        print("Tu dashboard es un archivo del repositorio: sobrevive a un")
        print("docker compose down y se recrea solo en cualquier maquina.\n")
        return 0

    print(f"\n{RED}{BOLD}{fallos} check(s) fallaron.{RESET}")
    print(f"\n{YELLOW}Sugerencias:{RESET}")
    print("  1. El provider relee la carpeta cada 30s. Espera y reintenta.")
    print("  2. Si Grafana no arranco con la configuracion nueva:")
    print("       docker compose up -d --force-recreate grafana")
    print("  3. Si el dashboard no aparece, suele ser sintaxis del JSON:")
    print("       docker compose logs grafana --tail 30")
    print("  4. Consulta docs/troubleshooting.md\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
