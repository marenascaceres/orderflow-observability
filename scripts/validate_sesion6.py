#!/usr/bin/env python3
"""
OrderFlow - Validador de la Sesion 6
=====================================
Comprueba que el entorno de Python puede consultar las dos fuentes
del curso, y que los notebooks estan completos y sin errores.

    python scripts/validate_sesion6.py

Solo depende de la stdlib de Python 3.8+. Las dependencias de los
notebooks (requests, pandas, elasticsearch...) se comprueban, pero
este script no las necesita para ejecutarse.
"""

import ast
import importlib.util
import json
import os
import re
import sys
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

PROMETHEUS = f"http://localhost:{os.getenv('PROMETHEUS_PORT', '9090')}"
ELASTIC = f"http://localhost:{os.getenv('ELASTICSEARCH_PORT', '9200')}"

REPO = Path(__file__).resolve().parent.parent
NOTEBOOKS = REPO / "notebooks"

METRICA_RE = re.compile(r"\b((?:orderflow|pg|redis)_[a-z0-9_]+)\b")

# Nombres sin prefijo que aparecian en el material antiguo. Si alguno
# sobrevive en un notebook, la consulta devuelve vacio en silencio.
NOMBRES_OBSOLETOS = [
    "orders_processed_total",
    "orders_failed_total",
    "order_processing_duration_seconds_bucket",
]


def _get(url: str, timeout: float = 8.0):
    req = urllib.request.Request(url, headers={"User-Agent": "orderflow-validator"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def _celdas_codigo(nb_path: Path):
    data = json.loads(nb_path.read_text(encoding="utf-8"))
    for i, c in enumerate(data.get("cells", [])):
        yield i, c.get("cell_type"), "".join(c.get("source", []))


# --------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------

def check_notebooks_presentes():
    if not NOTEBOOKS.is_dir():
        return False, "no existe la carpeta notebooks/"
    encontrados = sorted(p.name for p in NOTEBOOKS.glob("*.ipynb"))
    if len(encontrados) < 4:
        return False, f"solo {len(encontrados)} notebooks: {', '.join(encontrados)}"
    return True, f"{len(encontrados)} notebooks"


def check_sintaxis():
    """Una celda que no parsea rompe la clase en el peor momento."""
    errores = []
    for nb in sorted(NOTEBOOKS.glob("*.ipynb")):
        for i, tipo, src in _celdas_codigo(nb):
            if tipo != "code" or not src.strip():
                continue
            try:
                ast.parse(src)
            except SyntaxError as e:
                errores.append(f"{nb.name} celda {i} (linea {e.lineno})")
    if errores:
        return False, "; ".join(errores)
    return True, "todas las celdas de codigo parsean"


def check_nombres_obsoletos():
    """Ningun notebook debe usar los nombres sin prefijo."""
    encontrados = []
    for nb in sorted(NOTEBOOKS.glob("*.ipynb")):
        texto = nb.read_text(encoding="utf-8")
        for viejo in NOMBRES_OBSOLETOS:
            # Solo cuenta si NO va precedido de "orderflow_".
            if re.search(rf"(?<!orderflow_){re.escape(viejo)}", texto):
                encontrados.append(f"{nb.name}: {viejo}")
    if encontrados:
        return False, "; ".join(encontrados)
    return True, "ninguno"


def check_metricas_existen():
    citadas = set()
    for nb in sorted(NOTEBOOKS.glob("*.ipynb")):
        citadas.update(METRICA_RE.findall(nb.read_text(encoding="utf-8")))
    if not citadas:
        return False, "los notebooks no consultan ninguna metrica de OrderFlow"
    try:
        existentes = set(_get(f"{PROMETHEUS}/api/v1/label/__name__/values").get("data", []))
    except Exception as e:
        return False, f"Prometheus no responde ({type(e).__name__})"
    faltan = sorted(citadas - existentes)
    if faltan:
        return False, f"no existen en Prometheus: {', '.join(faltan)}"
    return True, f"{len(citadas)} metricas, todas existen"


def check_dependencias():
    faltan = [m for m in ("requests", "pandas", "matplotlib", "elasticsearch")
              if importlib.util.find_spec(m) is None]
    if faltan:
        return False, f"faltan: {', '.join(faltan)} (pip install -r notebooks/requirements.txt)"
    return True, "requests, pandas, matplotlib, elasticsearch"


def check_prometheus_api():
    try:
        data = _get(f"{PROMETHEUS}/api/v1/query?query=sum(orderflow_orders_processed_total)")
    except Exception as e:
        return False, f"Prometheus no responde ({type(e).__name__})"
    res = data.get("data", {}).get("result", [])
    if not res:
        return False, "la API responde pero no hay datos (deja correr el pipeline)"
    return True, f"total procesado: {float(res[0]['value'][1]):.0f}"


def check_elasticsearch_api():
    try:
        data = _get(f"{ELASTIC}/orderflow-logs-*/_count")
    except Exception as e:
        return False, f"Elasticsearch no responde ({type(e).__name__})"
    n = data.get("count", 0)
    if n == 0:
        return False, "el indice esta vacio"
    return True, f"{n} documentos"


def check_ejercicio_c():
    """Opcional: el alumno amplia el notebook 4 para notificar."""
    nb = NOTEBOOKS / "04_practica_final.ipynb"
    if not nb.exists():
        return None, "falta 04_practica_final.ipynb"
    codigo = "".join(src for _, tipo, src in _celdas_codigo(nb) if tipo == "code")
    if "informe_salud.txt" in codigo and "5001" in codigo:
        return True, "el informe se guarda y notifica al webhook"
    return None, "aun sin ampliar el notebook 4"


CHECKS = [
    ("Los 4 notebooks estan presentes", check_notebooks_presentes),
    ("Todas las celdas de codigo parsean", check_sintaxis),
    ("Sin nombres de metrica obsoletos", check_nombres_obsoletos),
    ("Las metricas citadas existen", check_metricas_existen),
    ("Dependencias de Python instaladas", check_dependencias),
    ("La API de Prometheus devuelve datos", check_prometheus_api),
    ("La API de Elasticsearch devuelve datos", check_elasticsearch_api),
    ("Ejercicio C: informe y notificacion", check_ejercicio_c),
]


def main() -> int:
    print(f"{BOLD}OrderFlow - Validador de la Sesion 6{RESET}\n")
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
        print(f"\n{GREEN}{BOLD}Sesion 6 completa. Fin del curso.{RESET}")
        print("Metricas y logs capturados, consultados por codigo y")
        print("convertidos en una decision. El mini proyecto esta en")
        print("docs/mini_proyecto.md\n")
        return 0

    print(f"\n{RED}{BOLD}{fallos} check(s) fallaron.{RESET}")
    print(f"\n{YELLOW}Sugerencias:{RESET}")
    print("  1. Instala las dependencias:")
    print("       pip install -r notebooks/requirements.txt")
    print("  2. Si una metrica 'no existe', casi siempre le falta el")
    print("     prefijo orderflow_. Comprueba en docs/metricas.md")
    print("  3. Consulta docs/troubleshooting.md\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
