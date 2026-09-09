#!/usr/bin/env python3
"""
Exporta los dashboards de Grafana a archivos del repositorio.

El provisioning de Grafana va en una sola direccion: del archivo hacia
Grafana, nunca al reves. Eso es deliberado —si Grafana pudiera reescribir
el archivo, el archivo dejaria de ser la fuente de verdad— pero deja un
paso manual: montar el panel a clics, abrir el JSON Model, copiar, pegar.

Este script hace ese paso. Le pide cada dashboard a la API de Grafana,
le quita lo que solo vale en esta instalacion, y escribe el archivo.

    Grafana --API--> este script --escribe--> repo --provisioning--> Grafana

Lo que NO hace, a proposito: subir nada a git. Ese paso sigue siendo tuyo,
y es donde entra la revision. El script quita el trabajo mecanico, no la
decision.

Uso:
    python scripts/exportar_dashboards.py                 # carpeta OrderFlow
    python scripts/exportar_dashboards.py --carpeta Ventas
    python scripts/exportar_dashboards.py --uid mi-panel  # solo uno
    python scripts/exportar_dashboards.py --todos         # todas las carpetas

Y el caso que aparece en cuanto hay un solo Grafana: el dashboard que esta
provisionado no se puede editar a clics —el provider lo devuelve al estado
del archivo cada 30 segundos— asi que se trabaja sobre una copia y se
vuelca sobre el original:

    python scripts/exportar_dashboards.py --uid <uid-del-borrador> --como orderflow-overview

Eso escribe el borrador en orderflow-overview.json, con ese uid y sin el
sufijo "(borrador)" del titulo. El provider lo aplica en 30 segundos.

En un equipo con varios entornos esto no hace falta: se edita en un
Grafana de desarrollo sin provisioning y se provisiona en produccion, con
lo que el que edita y el que se provisiona nunca son el mismo.

Sin dependencias: solo la biblioteca estandar, como el resto de scripts
del curso.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DESTINO = REPO / "grafana" / "dashboards"


def _cargar_env() -> None:
    """Lee el .env del repositorio, igual que hace docker compose.

    Sin esto usariamos siempre admin/admin, y Grafana obliga a cambiar la
    contrasena en el primer inicio de sesion. No pisa lo que ya venga del
    entorno, para que siga sirviendo:

        $env:GRAFANA_ADMIN_PASSWORD = "otra"; python scripts/exportar_dashboards.py
    """
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

GRAFANA = f"http://localhost:{os.getenv('GRAFANA_PORT', '3000')}"
USER = os.getenv("GRAFANA_ADMIN_USER", "admin")
PASSWORD = os.getenv("GRAFANA_ADMIN_PASSWORD", "admin")

# Un uid generado por Grafana son ~14 caracteres sin ninguna vocal que
# forme palabra: "afxop4h0b5ds0f". Uno puesto a mano se lee y lleva
# guiones: "orderflow-overview". La distincion no es exacta y no hace
# falta que lo sea: solo sirve para avisar.
UID_AUTOGENERADO = re.compile(r"^[a-z0-9]{12,}$")

# Claves que Grafana usa para su propia contabilidad y que no significan
# nada en otra instalacion.
#
# "version" NO se quita, aunque cambie en cada guardado y ensucie el diff
# con una linea. Grafana la incrementa al guardar, y un dashboard
# provisionado desde un archivo que no la trae falla al editarlo desde la
# interfaz:
#
#     Cannot assign to read only property 'version' of object
#
# Es el limite de normalizar: se puede quitar lo que sobra, no lo que la
# herramienta necesita para funcionar.
CLAVES_LOCALES = ("iteration",)

VERDE, ROJO, AMARILLO, GRIS, FIN = "\033[92m", "\033[91m", "\033[93m", "\033[90m", "\033[0m"
if os.name == "nt" and not os.getenv("WT_SESSION"):
    VERDE = ROJO = AMARILLO = GRIS = FIN = ""


def _api(ruta: str):
    url = f"{GRAFANA}{ruta}"
    token = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {token}",
            "User-Agent": "orderflow-exportador",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _uid_carpeta(nombre: str) -> str | None:
    """El uid de una carpeta a partir de su nombre visible."""
    for f in _api("/api/folders"):
        if f.get("title", "").lower() == nombre.lower():
            return f.get("uid")
    return None


def _listar(carpeta: str | None, todos: bool) -> list[dict]:
    if todos:
        return [d for d in _api("/api/search?type=dash-db")]
    uid = _uid_carpeta(carpeta)
    if uid is None:
        print(f"{ROJO}No existe ninguna carpeta llamada '{carpeta}'.{FIN}")
        print("Carpetas disponibles: " + ", ".join(
            f.get("title", "?") for f in _api("/api/folders")) or "(ninguna)")
        sys.exit(1)
    ruta = "/api/search?type=dash-db&" + urllib.parse.urlencode({"folderUIDs": uid})
    return list(_api(ruta))


def _ordenar_paneles(panel: dict) -> None:
    """Ordena los paneles por su id, que es lo unico que no cambia nunca.

    Grafana devuelve el array en el orden que le viene bien, y ese orden
    cambia al insertar o mover un panel. Como git compara linea a linea,
    un reordenamiento hace que TODOS aparezcan modificados aunque nadie
    los haya tocado: anadir un panel de 40 lineas producia un diff de 300.

    Un diff que no se puede leer es un diff que nadie revisa. Y el dia que
    se cuele un umbral cambiado, pasara sin que nadie lo vea.

    Se ordena por id y no por posicion en pantalla —que seria lo
    intuitivo— porque el id no cambia jamas: ni al mover el panel, ni al
    redimensionarlo, ni al insertar otro delante. Con el orden visual,
    intercambiar dos paneles reescribia los dos bloques enteros: treinta
    lineas de diff para decir que dos coordenadas cambiaron. Ordenando por
    id, ese mismo cambio son cuatro lineas.

    Se pierde que el archivo siga el orden de la pantalla, y no importa:
    para ver el dashboard esta Grafana. El archivo existe para revisar
    cambios.

    Reordenar aqui es seguro: Grafana coloca cada panel por su gridPos, no
    por su posicion en el array.
    """
    paneles = panel.get("panels")
    if not isinstance(paneles, list):
        return
    panel["panels"] = sorted(paneles, key=lambda p: p.get("id", 0))


def _limpiar(panel: dict) -> dict:
    """Deja el dashboard listo para vivir en el repositorio."""
    for clave in CLAVES_LOCALES:
        panel.pop(clave, None)
    _ordenar_paneles(panel)
    # "id": null, no ausente: es lo que el manual pide comprobar y lo que
    # espera el validador de la Sesion 4.
    #
    # Se asigna sin hacer pop antes, a proposito. En Python un diccionario
    # conserva el orden de insercion, asi que borrar la clave y volver a
    # ponerla la manda al final del archivo: dos lineas de diff que no
    # significan nada y que estorban al revisar un cambio de verdad.
    panel["id"] = None
    return panel


def exportar(carpeta: str | None, todos: bool, uid_suelto: str | None,
             como: str | None = None, titulo: str | None = None) -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)

    try:
        if uid_suelto:
            encontrados = [{"uid": uid_suelto, "title": uid_suelto}]
        else:
            encontrados = _listar(carpeta, todos)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print(f"{ROJO}Grafana rechaza las credenciales.{FIN}")
            print("Si cambiaste la contrasena al entrar por primera vez, pasala asi:")
            print('  $env:GRAFANA_ADMIN_PASSWORD = "la_que_pusiste"; '
                  "python scripts/exportar_dashboards.py")
            return 1
        raise
    except urllib.error.URLError:
        print(f"{ROJO}Grafana no responde en {GRAFANA}.{FIN}")
        print("Comprueba que el stack esta levantado: docker compose ps")
        return 1

    if not encontrados:
        destino = "todas las carpetas" if todos else f"la carpeta '{carpeta}'"
        print(f"{AMARILLO}No hay ningun dashboard en {destino}.{FIN}")
        return 0

    print(f"Exportando a {GRIS}{DESTINO.relative_to(REPO)}{FIN}\n")

    escritos, avisos = [], []
    for d in encontrados:
        uid = d["uid"]
        try:
            payload = _api(f"/api/dashboards/uid/{uid}")
        except urllib.error.HTTPError:
            print(f"  {ROJO}x{FIN} {uid}: no se pudo leer")
            continue

        # La respuesta trae dos partes: "meta" (quien lo creo, cuando, en
        # que carpeta) y "dashboard" (el contenido). Solo la segunda vale
        # fuera de esta instalacion.
        panel = _limpiar(payload["dashboard"])

        # --como: exportar un borrador con la identidad del dashboard que
        # esta provisionado. Es el puente que falta cuando solo hay un
        # Grafana: el provisionado no se puede editar a clics, asi que se
        # trabaja sobre una copia y se vuelca sobre el original.
        destino_uid = como or uid
        if como:
            panel["uid"] = como
        if titulo:
            panel["title"] = titulo
        elif como:
            # Quita el sufijo de trabajo, si lo lleva.
            panel["title"] = re.sub(r"\s*\((borrador|copia|draft)\)\s*$", "",
                                    panel.get("title", ""), flags=re.I)

        titulo_final = panel.get("title", destino_uid)

        archivo = DESTINO / f"{destino_uid}.json"
        texto = json.dumps(panel, indent=2, ensure_ascii=False) + "\n"

        if archivo.exists() and archivo.read_text(encoding="utf-8") == texto:
            print(f"  {GRIS}={FIN} {archivo.name:<38} {GRIS}sin cambios{FIN}")
        else:
            archivo.write_text(texto, encoding="utf-8")
            n = len(panel.get("panels", []))
            print(f"  {VERDE}+{FIN} {archivo.name:<38} {titulo_final}  ({n} paneles)")

        escritos.append(archivo.name)

        if UID_AUTOGENERADO.match(destino_uid):
            avisos.append((destino_uid, titulo_final))

    # Archivos que ya no corresponden a ningun dashboard. No se borran:
    # puede que sean de otra carpeta, o que alguien los este escribiendo
    # a mano. Solo se avisa.
    huerfanos = [f.name for f in DESTINO.glob("*.json") if f.name not in escritos]

    if avisos:
        print(f"\n{AMARILLO}Estos dashboards tienen un uid que genero Grafana:{FIN}")
        for uid, titulo in avisos:
            print(f"  {uid}  ->  {titulo}")
        print("  Funcionan igual, pero dentro de seis meses nadie sabra que")
        print("  contiene 'afxop4h0b5ds0f.json'. Se cambia en Grafana, en")
        print("  Dashboard settings -> JSON Model, por algo legible.")

    if huerfanos and not uid_suelto:
        print(f"\n{AMARILLO}Archivos que ya no corresponden a ningun dashboard:{FIN}")
        for h in huerfanos:
            print(f"  {h}")
        print("  Revisalos antes de borrarlos: pueden ser de otra carpeta.")

    print(f"\n{VERDE}{len(escritos)} dashboard(s) exportado(s).{FIN}")
    print("El provider los relee en 30 segundos. Revisa el diff antes de subirlos:")
    print(f"  {GRIS}git diff grafana/dashboards/{FIN}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Exporta los dashboards de Grafana a archivos del repositorio.")
    p.add_argument("--carpeta", default="OrderFlow",
                   help="Carpeta de Grafana a exportar (por defecto: OrderFlow)")
    p.add_argument("--todos", action="store_true",
                   help="Exportar los de todas las carpetas")
    p.add_argument("--uid", dest="uid_suelto",
                   help="Exportar un unico dashboard por su uid")
    p.add_argument("--como",
                   help="Guardarlo con este uid, no con el suyo. Sirve para "
                        "volcar un borrador sobre el dashboard provisionado")
    p.add_argument("--titulo",
                   help="Titulo con el que guardarlo (por defecto, el suyo sin "
                        "el sufijo (borrador))")
    args = p.parse_args()
    if args.como and not args.uid_suelto:
        p.error("--como necesita que digas cual exportar, con --uid")
    return exportar(args.carpeta, args.todos, args.uid_suelto, args.como, args.titulo)


if __name__ == "__main__":
    sys.exit(main())
