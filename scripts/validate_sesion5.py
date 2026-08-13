#!/usr/bin/env python3
"""
OrderFlow - Validador de la Sesion 5
=====================================
Comprueba que la cadena completa de alertas esta en pie: reglas
cargadas en Prometheus, Alertmanager enrutando, y los dos destinos
de notificacion respondiendo.

    python scripts/validate_sesion5.py

Solo depende de la stdlib de Python 3.8+.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"

PROMETHEUS = f"http://localhost:{os.getenv('PROMETHEUS_PORT', '9090')}"
ALERTMANAGER = f"http://localhost:{os.getenv('ALERTMANAGER_PORT', '9093')}"
MAILHOG = f"http://localhost:{os.getenv('MAILHOG_UI_PORT', '8025')}"
WEBHOOK = f"http://localhost:{os.getenv('WEBHOOK_PORT', '5001')}"

METRICA_RE = re.compile(r"\b((?:orderflow|pg|redis)_[a-z0-9_]+)\b")

# Las tres que vienen resueltas en el repo. La cuarta la escribe el
# alumno en el Ejercicio B y se comprueba aparte, sin hacer fallar.
REGLAS_BASE = {"ProcessorCaido", "GeneratorCaido", "TasaErrorAlta", "LatenciaAltaP95"}
REGLA_EJERCICIO = "SinOrdenesProcesadas"


def _get(url: str, timeout: float = 8.0):
    req = urllib.request.Request(url, headers={"User-Agent": "orderflow-validator"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def _reglas():
    """Devuelve {nombre: expr} de todas las reglas de alerta cargadas."""
    data = _get(f"{PROMETHEUS}/api/v1/rules")
    reglas = {}
    for grupo in data.get("data", {}).get("groups", []):
        for r in grupo.get("rules", []):
            if r.get("type") == "alerting":
                reglas[r.get("name")] = r.get("query", "")
    return reglas


# --------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------

def check_reglas_cargadas():
    try:
        reglas = _reglas()
    except Exception as e:
        return False, f"Prometheus no responde ({type(e).__name__})"
    if not reglas:
        return False, "no hay ninguna regla cargada (recarga con /-/reload)"
    faltan = REGLAS_BASE - set(reglas)
    if faltan:
        return False, f"faltan reglas: {', '.join(sorted(faltan))}"
    return True, f"{len(reglas)} reglas: {', '.join(sorted(reglas))}"


def check_metricas_de_las_reglas():
    """Una regla con un nombre de metrica inexistente no da error: no
    dispara nunca. Es el fallo mas caro de esta sesion."""
    try:
        reglas = _reglas()
    except Exception as e:
        return False, f"Prometheus no responde ({type(e).__name__})"
    if not reglas:
        return False, "no hay reglas que comprobar"

    citadas = set()
    for expr in reglas.values():
        citadas.update(METRICA_RE.findall(expr))
    if not citadas:
        return False, "ninguna regla consulta una metrica de OrderFlow"

    try:
        existentes = set(_get(f"{PROMETHEUS}/api/v1/label/__name__/values").get("data", []))
    except Exception as e:
        return False, f"Prometheus no responde ({type(e).__name__})"

    faltan = sorted(citadas - existentes)
    if faltan:
        return False, f"no existen en Prometheus: {', '.join(faltan)}"
    return True, f"{len(citadas)} metricas, todas existen"


def check_alertmanager_conocido():
    """Sin esto, Prometheus detecta el problema y no se lo cuenta a nadie."""
    try:
        data = _get(f"{PROMETHEUS}/api/v1/alertmanagers")
    except Exception as e:
        return False, f"Prometheus no responde ({type(e).__name__})"
    activos = data.get("data", {}).get("activeAlertmanagers", [])
    if not activos:
        return False, "Prometheus no tiene ningun Alertmanager activo"
    return True, activos[0].get("url", "")


def check_alertmanager_config():
    try:
        data = _get(f"{ALERTMANAGER}/api/v2/status")
    except Exception as e:
        return False, f"Alertmanager no responde ({type(e).__name__})"
    config = data.get("config", {}).get("original", "")
    faltan = [r for r in ("equipo-datos-email", "guardia-webhook") if r not in config]
    if faltan:
        return False, f"receivers ausentes: {', '.join(faltan)}"
    if "inhibit_rules" not in config:
        return False, "no hay reglas de inhibicion configuradas"
    return True, "2 receivers + inhibicion"


def check_ruta_final_sin_matchers():
    """El fallo silencioso del Paso 9: si la ultima ruta filtra por
    warning|info, las criticas nunca llegan al correo."""
    try:
        data = _get(f"{ALERTMANAGER}/api/v2/status")
    except Exception as e:
        return False, f"Alertmanager no responde ({type(e).__name__})"
    config = data.get("config", {}).get("original", "")
    if re.search(r'severity=~"warning\|info"', config):
        return False, "la ruta final filtra warning|info: las criticas no llegan al correo"
    return True, "las alertas criticas llegan a los dos canales"


def check_mailhog():
    try:
        data = _get(f"{MAILHOG}/api/v2/messages")
    except Exception as e:
        return False, f"MailHog no responde en {MAILHOG} ({type(e).__name__})"
    return True, f"buzon accesible, {data.get('total', 0)} correos"


def check_webhook():
    try:
        data = _get(f"{WEBHOOK}/health")
    except Exception as e:
        return False, f"webhook-receiver no responde ({type(e).__name__})"
    if data.get("status") != "up":
        return False, f"estado '{data.get('status')}'"
    return True, "responde en /health"


def check_notificacion_recibida():
    """Opcional: solo da OK si el alumno ya provoco el incidente."""
    correos = 0
    alertas = 0
    try:
        correos = _get(f"{MAILHOG}/api/v2/messages").get("total", 0)
    except Exception:
        pass
    try:
        alertas = _get(f"{WEBHOOK}/alertas").get("total", 0)
    except Exception:
        pass
    if correos or alertas:
        return True, f"{correos} correo(s), {alertas} payload(s) en el webhook"
    return None, "aun no llego ninguna notificacion (Bloque 3)"


def check_regla_ejercicio():
    try:
        reglas = _reglas()
    except Exception as e:
        return None, f"Prometheus no responde ({type(e).__name__})"
    if REGLA_EJERCICIO in reglas:
        return True, f"{REGLA_EJERCICIO} cargada"
    return None, f"aun sin escribir {REGLA_EJERCICIO}"


CHECKS = [
    ("Reglas de alerta cargadas", check_reglas_cargadas),
    ("Las metricas de las reglas existen", check_metricas_de_las_reglas),
    ("Prometheus conoce un Alertmanager", check_alertmanager_conocido),
    ("Alertmanager: receivers e inhibicion", check_alertmanager_config),
    ("La ruta final no filtra por severidad", check_ruta_final_sin_matchers),
    ("MailHog responde", check_mailhog),
    ("webhook-receiver responde", check_webhook),
    ("Llego alguna notificacion", check_notificacion_recibida),
    ("Ejercicio B: SinOrdenesProcesadas", check_regla_ejercicio),
]


def main() -> int:
    print(f"{BOLD}OrderFlow - Validador de la Sesion 5{RESET}\n")
    print(f"{'Check':<44} {'Estado':<10} Detalle")
    print("-" * 100)

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

    print("-" * 100)

    if fallos == 0:
        print(f"\n{GREEN}{BOLD}Sesion 5 completa. Alertmanager ya no esta vacio.{RESET}")
        print("El sistema avisa solo: ya no hace falta estar mirando.\n")
        return 0

    print(f"\n{RED}{BOLD}{fallos} check(s) fallaron.{RESET}")
    print(f"\n{YELLOW}Sugerencias:{RESET}")
    print("  1. Tras editar las reglas hay que recargar:")
    print("       curl -X POST http://localhost:9090/-/reload")
    print("       curl -X POST http://localhost:9093/-/reload")
    print("  2. Si falta algun servicio nuevo:")
    print("       docker compose up -d --build")
    print("  3. Si una regla no aparece, suele ser sangria del YAML:")
    print("       docker compose logs prometheus --tail 30")
    print("  4. Consulta docs/troubleshooting.md\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
