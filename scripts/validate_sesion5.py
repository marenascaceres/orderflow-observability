#!/usr/bin/env python3
"""
OrderFlow - Validador de la Sesion 5
=====================================
Comprueba que la cadena completa de alertas esta en pie: reglas
cargadas en Prometheus, Alertmanager enrutando, el correo configurado
sin la contrasena a la vista, el webhook respondiendo y la regla
equivalente cargada en Grafana.

    python scripts/validate_sesion5.py

Si cambiaste la contrasena de Grafana y no esta en tu .env:
    $env:GRAFANA_ADMIN_PASSWORD = "la_tuya"; python scripts/validate_sesion5.py

Solo depende de la stdlib de Python 3.8+.
"""

import base64
import json
import os
import re
import sys
import urllib.error
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

REPO = Path(__file__).resolve().parent.parent


def _cargar_env() -> None:
    """Lee el .env del repositorio, igual que hace docker compose (mismo
    criterio que validate_sesion4.py). No sobrescribe lo que ya venga
    del entorno."""
    env = REPO / ".env"
    if not env.exists():
        return
    for linea in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip())


_cargar_env()

PROMETHEUS = f"http://localhost:{os.getenv('PROMETHEUS_PORT', '9090')}"
ALERTMANAGER = f"http://localhost:{os.getenv('ALERTMANAGER_PORT', '9093')}"
WEBHOOK = f"http://localhost:{os.getenv('WEBHOOK_PORT', '5001')}"
GRAFANA = f"http://localhost:{os.getenv('GRAFANA_PORT', '3000')}"
GRAFANA_USER = os.getenv("GRAFANA_ADMIN_USER", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_ADMIN_PASSWORD", "admin")

# Archivo con la contrasena del correo. Vive fuera de git.
SMTP_PASSWORD = REPO / "alertmanager" / "smtp_password"
# uid y nombre fijados en grafana/provisioning/alerting/orderflow-alerts.yml
GRAFANA_REGLA_UID = "of-tasa-error"
GRAFANA_CONTACTO = "equipo-datos"

METRICA_RE = re.compile(r"\b((?:orderflow|pg|redis)_[a-z0-9_]+)\b")

# Las cuatro que vienen resueltas en alerts.yml. La quinta la escribe el
# alumno en el Ejercicio B y se comprueba aparte, sin hacer fallar.
REGLAS_BASE = {"ProcessorCaido", "GeneratorCaido", "TasaErrorAlta", "LatenciaAltaP95"}
REGLA_EJERCICIO = "SinOrdenesProcesadas"


def _get(url: str, auth: bool = False, timeout: float = 8.0):
    req = urllib.request.Request(url, headers={"User-Agent": "orderflow-validator"})
    if auth:
        token = base64.b64encode(f"{GRAFANA_USER}:{GRAFANA_PASSWORD}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
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
        # Los valores entre comillas no son nombres de metrica. Sin esta
        # limpieza, un filtro como {datname="orderflow_dw"} se leeria como
        # una metrica inexistente y el validador daria FAIL a quien lo
        # hubiera hecho todo bien. (Mismo fallo corregido en la Sesion 4.)
        citadas.update(METRICA_RE.findall(re.sub(r'"[^"]*"', '""', expr)))
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


def check_correo_seguro():
    """El correo real necesita una contrasena. Este check no la lee: solo
    comprueba que no esta escrita en alertmanager.yml y que el archivo
    donde vive no se puede subir a git por descuido."""
    try:
        data = _get(f"{ALERTMANAGER}/api/v2/status")
    except Exception as e:
        return False, f"Alertmanager no responde ({type(e).__name__})"
    config = data.get("config", {}).get("original", "")

    if "TU_CORREO" in config:
        return False, "quedan TU_CORREO sin reemplazar en alertmanager.yml"
    # Una contrasena escrita en el YAML aparece como <secret> en la API.
    if re.search(r"^\s*smtp_auth_password:", config, re.MULTILINE):
        return False, "la contrasena esta escrita en alertmanager.yml: usa smtp_auth_password_file"
    if "smtp_auth_password_file" not in config:
        return False, "Alertmanager no tiene smtp_auth_password_file configurado"

    if not SMTP_PASSWORD.exists() or SMTP_PASSWORD.stat().st_size == 0:
        return False, "falta alertmanager/smtp_password o esta vacio"
    gitignore = REPO / ".gitignore"
    ignorados = gitignore.read_text(encoding="utf-8", errors="ignore") if gitignore.exists() else ""
    if "alertmanager/smtp_password" not in [l.strip() for l in ignorados.splitlines()]:
        return False, "alertmanager/smtp_password no esta en .gitignore"
    return True, "contrasena en archivo aparte, protegido por .gitignore"


def check_webhook():
    try:
        data = _get(f"{WEBHOOK}/health")
    except Exception as e:
        return False, f"webhook-receiver no responde ({type(e).__name__})"
    if data.get("status") != "up":
        return False, f"estado '{data.get('status')}'"
    return True, "responde en /health"


def check_notificacion_recibida():
    """Opcional: solo da OK si el alumno ya provoco el incidente. Solo
    mira el webhook: los correos llegan a Gmail y no se pueden consultar
    desde aqui."""
    try:
        alertas = _get(f"{WEBHOOK}/alertas").get("total", 0)
    except Exception:
        alertas = 0
    if alertas:
        return True, f"{alertas} aviso(s) recibidos en el webhook"
    return None, "aun no llego ningun aviso al webhook (Bloque 3)"


def check_grafana_alerta():
    """La regla y el punto de contacto de orderflow-alerts.yml. Si el
    archivo esta en otra carpeta, Grafana lo ignora sin avisar."""
    try:
        regla = _get(f"{GRAFANA}/api/v1/provisioning/alert-rules/{GRAFANA_REGLA_UID}", auth=True)
        contactos = _get(f"{GRAFANA}/api/v1/provisioning/contact-points", auth=True)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, ("no existe la regla: revisa que orderflow-alerts.yml este en "
                           "grafana/provisioning/alerting y reinicia Grafana")
        if e.code == 401:
            return False, "credenciales de Grafana incorrectas (GRAFANA_ADMIN_PASSWORD)"
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, f"Grafana no responde ({type(e).__name__})"
    if not any(c.get("name") == GRAFANA_CONTACTO for c in contactos):
        return False, f"la regla existe pero falta el punto de contacto '{GRAFANA_CONTACTO}'"
    return True, f"{regla.get('title')} + punto de contacto {GRAFANA_CONTACTO}"


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
    ("Correo sin contrasena a la vista", check_correo_seguro),
    ("webhook-receiver responde", check_webhook),
    ("Llego algun aviso al webhook", check_notificacion_recibida),
    ("Grafana: regla y punto de contacto", check_grafana_alerta),
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
    print("  1. Tras editar las reglas hay que recargar (PowerShell):")
    print("       Invoke-RestMethod -Method Post http://localhost:9090/-/reload")
    print("       Invoke-RestMethod -Method Post http://localhost:9093/-/reload")
    print("     En Linux o Mac: curl -X POST <la misma direccion>")
    print("  2. Si falta algun servicio nuevo:")
    print("       docker compose up -d --build")
    print("  3. Si una regla no aparece, suele ser sangria del YAML:")
    print("       docker compose logs prometheus --tail 30")
    print("  4. Si falla la comprobacion de Grafana, tras copiar el archivo:")
    print("       docker compose restart grafana")
    print("  5. Consulta docs/troubleshooting.md\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
