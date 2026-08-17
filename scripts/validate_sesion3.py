#!/usr/bin/env python3
"""
OrderFlow - Validador de la Sesion 3
=====================================
Comprueba que los DOS origenes de logs llegan a Elasticsearch, que el
texto plano del generator quedo estructurado por grok, y que no hay
fallos silenciosos de parseo.

    python scripts/validate_sesion3.py

Solo depende de la stdlib de Python 3.8+.
"""

import json
import sys
import urllib.parse
import urllib.request

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

ES = "http://localhost:9200"
INDICE = "orderflow-logs-*"


def get_json(url: str, timeout: float = 8.0):
    req = urllib.request.Request(url, headers={"User-Agent": "orderflow-validator"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def contar(query: str) -> int:
    """Numero de documentos que casan con una query_string de Lucene."""
    url = f"{ES}/{INDICE}/_count?q={urllib.parse.quote(query)}"
    return int(get_json(url).get("count", 0))


def check_indice():
    try:
        total = contar("*")
    except Exception as e:
        return False, f"Elasticsearch no responde ({type(e).__name__})"
    if total == 0:
        return False, "el indice existe pero esta vacio (espera 60s tras arrancar)"
    return True, f"{total} documentos"


def check_origen(tag: str, nombre: str):
    try:
        n = contar(f"tags:{tag}")
    except Exception as e:
        return False, f"Elasticsearch no responde ({type(e).__name__})"
    if n == 0:
        return False, f"no llega ningun log de {nombre}"
    return True, f"{n} documentos"


def check_grok_estructurado():
    """Los logs del generator deben tener los campos que extrajo grok.

    Si llegan pero sin campos, el input funciona y el filtro no.
    """
    try:
        n_total = contar("tags:generator")
        n_con_campos = contar("tags:generator AND event:order_generated AND _exists_:region")
    except Exception as e:
        return False, f"Elasticsearch no responde ({type(e).__name__})"

    if n_total == 0:
        return False, "no hay logs del generator que comprobar"
    if n_con_campos == 0:
        return False, "los logs llegan pero grok no extrajo los campos"
    return True, f"{n_con_campos} documentos con region/total_amount"


def check_sin_fallo(tag: str, explicacion: str):
    try:
        n = contar(f"tags:{tag}")
    except Exception as e:
        return False, f"Elasticsearch no responde ({type(e).__name__})"
    if n > 0:
        return False, f"{n} documentos con {tag} ({explicacion})"
    return True, "ninguno"


def check_correlacion():
    """Los dos origenes deben convivir en el mismo indice.

    Es lo que permite cruzarlos en una sola consulta de Kibana.
    """
    try:
        gen = contar("tags:generator")
        proc = contar("tags:processor")
    except Exception as e:
        return False, f"Elasticsearch no responde ({type(e).__name__})"
    if gen > 0 and proc > 0:
        return True, f"generator={gen}, processor={proc}, mismo indice"
    return False, "falta uno de los dos origenes"


CHECKS = [
    ("Indice orderflow-logs-* con datos", check_indice),
    ("Logs del order-processor (TCP/JSON)", lambda: check_origen("processor", "order-processor")),
    ("Logs del order-generator (syslog)", lambda: check_origen("generator", "order-generator")),
    ("grok estructuro el texto plano", check_grok_estructurado),
    ("Sin fallos de grok", lambda: check_sin_fallo("_grokparsefailure", "el patron no casa con el texto")),
    ("Sin fallos de fecha", lambda: check_sin_fallo("_dateparsefailure", "revisa el filtro date")),
    ("Ambos origenes en el mismo indice", check_correlacion),
]


def main() -> int:
    print(f"{BOLD}OrderFlow - Validador de la Sesion 3{RESET}\n")
    print(f"{'Check':<48} {'Estado':<10} Detalle")
    print("-" * 92)

    fallos = 0
    for nombre, check in CHECKS:
        try:
            ok, detalle = check()
        except Exception as e:
            ok, detalle = False, f"excepcion: {e}"
        estado = f"{GREEN}OK{RESET}" if ok else f"{RED}FAIL{RESET}"
        if not ok:
            fallos += 1
        print(f"{nombre:<48} {estado:<19} {detalle}")

    print("-" * 92)

    if fallos == 0:
        print(f"\n{GREEN}{BOLD}Sesion 3 completa. Kibana ya no esta vacio.{RESET}")
        print("Los dos origenes de logs conviven estructurados en el mismo indice.\n")
        return 0

    print(f"\n{RED}{BOLD}{fallos} check(s) fallaron.{RESET}")
    print(f"\n{YELLOW}Sugerencias:{RESET}")
    print("  1. Logstash tarda ~60s en arrancar. Espera y reintenta.")
    print("  2. Si no llegan logs del generator, el driver de logging no se aplico:")
    print("       docker compose up -d --force-recreate order-generator")
    print("  3. Si Logstash no arranca, suele ser sintaxis del pipeline:")
    print("       docker compose logs logstash --tail 40")
    print("  4. Consulta docs/troubleshooting.md\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
