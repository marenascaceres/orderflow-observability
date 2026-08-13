#!/usr/bin/env python3
"""
OrderFlow - Webhook receiver de prueba para Alertmanager
=========================================================
Anadido en la Sesion 5.

Recibe el POST que Alertmanager envia cuando una alerta se dispara o
se resuelve, y lo imprime formateado en los logs del contenedor:

    docker compose logs -f webhook-receiver

Su unica razon de existir es pedagogica: que se vea el JSON real de
una alerta. Ese mismo payload es el que recibiria Slack, PagerDuty o
un sistema de tickets. Entenderlo aqui es entenderlo en todas partes.
"""

import json
import os
from datetime import datetime

from flask import Flask, request

app = Flask(__name__)

# Cada payload crudo se guarda ademas en un archivo, para poder
# revisarlo despues aunque los logs se hayan perdido de vista.
LOG_PATH = os.getenv("ALERTAS_LOG", "/tmp/alertas_recibidas.log")


@app.route("/alertas", methods=["POST"])
def alertas():
    payload = request.get_json(force=True, silent=True) or {}
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n===== ALERTA RECIBIDA @ {ts} =====", flush=True)
    print(f"  status global : {payload.get('status')}", flush=True)
    print(f"  receiver      : {payload.get('receiver')}", flush=True)

    for a in payload.get("alerts", []):
        labels = a.get("labels", {})
        ann = a.get("annotations", {})
        print("-" * 52, flush=True)
        print(f"  estado    : {a.get('status')}", flush=True)
        print(f"  alerta    : {labels.get('alertname')}", flush=True)
        print(f"  severidad : {labels.get('severity')}", flush=True)
        print(f"  servicio  : {labels.get('service')}", flush=True)
        print(f"  resumen   : {ann.get('summary')}", flush=True)
        print(f"  detalle   : {ann.get('description')}", flush=True)

    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError as e:
        # Que no se pueda escribir el archivo no debe hacer fallar la
        # entrega: Alertmanager reintentaria una y otra vez.
        print(f"  (aviso: no se pudo escribir {LOG_PATH}: {e})", flush=True)

    return {"ok": True}, 200


@app.route("/alertas", methods=["GET"])
def alertas_recibidas():
    """Devuelve las alertas guardadas. Lo usa scripts/validate_sesion5.py."""
    try:
        with open(LOG_PATH, encoding="utf-8") as f:
            lineas = [json.loads(l) for l in f if l.strip()]
    except FileNotFoundError:
        lineas = []
    return {"total": len(lineas), "alertas": lineas}, 200


@app.route("/health", methods=["GET"])
def health():
    return {"status": "up"}, 200


if __name__ == "__main__":
    # 0.0.0.0 para que Alertmanager, que corre en otro contenedor,
    # pueda alcanzarlo por el nombre de servicio de la red de Compose.
    app.run(host="0.0.0.0", port=5001)
