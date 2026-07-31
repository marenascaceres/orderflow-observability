"""
OrderFlow - Order Generator
============================
Simula el sistema transaccional de un e-commerce: genera ordenes
sinteticas y las publica en Redis para que el processor las consuma.

Emite:
  - Metricas Prometheus en el puerto 8000/metrics
  - Logs de texto plano a stdout (intencional: contraste con processor
    que emite JSON estructurado -- material didactico para Sesion 1)
"""

import json
import logging
import os
import random
import sys
import time
import uuid
from datetime import datetime, timezone

import redis
from prometheus_client import Counter, Gauge, start_http_server

# ============================================================
# Configuracion desde variables de entorno
# ============================================================
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
GENERATION_INTERVAL_SEC = float(os.getenv("GENERATION_INTERVAL_SEC", "1"))
METRICS_PORT = int(os.getenv("METRICS_PORT", "8000"))
QUEUE_NAME = "orders_queue"

# ============================================================
# Logging (texto plano, intencional)
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("generator")

# ============================================================
# Metricas Prometheus
# ============================================================
orders_generated = Counter(
    "orderflow_orders_generated_total",
    "Total de ordenes generadas y publicadas en la cola",
    ["region"],
)
generator_up = Gauge(
    "orderflow_generator_up",
    "1 si el generator esta produciendo, 0 si no",
)

# ============================================================
# Datos sinteticos
# ============================================================
REGIONS = ["lima", "arequipa", "cusco", "trujillo", "piura"]
PRODUCT_CATALOG = [
    ("SKU-001", "Zapatillas running", 89.90),
    ("SKU-002", "Camiseta algodon", 24.50),
    ("SKU-003", "Mochila urbana", 65.00),
    ("SKU-004", "Auriculares BT", 45.75),
    ("SKU-005", "Cuaderno A5", 8.90),
    ("SKU-006", "Botella termica", 32.00),
    ("SKU-007", "Cargador rapido", 27.50),
    ("SKU-008", "Libro tecnico", 55.00),
]


def build_order() -> dict:
    """Construye una orden sintetica con estructura realista."""
    num_items = random.randint(1, 5)
    items = []
    total = 0.0
    for _ in range(num_items):
        sku, name, unit_price = random.choice(PRODUCT_CATALOG)
        qty = random.randint(1, 3)
        line_total = round(unit_price * qty, 2)
        items.append({"sku": sku, "name": name, "qty": qty, "unit_price": unit_price, "line_total": line_total})
        total += line_total

    return {
        "order_id": str(uuid.uuid4()),
        "customer_id": f"CUST-{random.randint(1000, 9999)}",
        "region": random.choice(REGIONS),
        "items": items,
        "total_amount": round(total, 2),
        "currency": "PEN",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def connect_redis() -> redis.Redis:
    """Conecta a Redis con reintentos exponenciales."""
    attempt = 0
    while True:
        try:
            client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            client.ping()
            log.info(f"Conectado a Redis en {REDIS_HOST}:{REDIS_PORT}")
            return client
        except redis.exceptions.ConnectionError as e:
            attempt += 1
            wait = min(2 ** attempt, 30)
            log.warning(f"Redis no disponible (intento {attempt}): {e}. Reintentando en {wait}s...")
            time.sleep(wait)


def main() -> None:
    log.info("Iniciando order-generator")
    log.info(f"Configuracion: intervalo={GENERATION_INTERVAL_SEC}s, metrics_port={METRICS_PORT}")

    # Servidor HTTP de metricas Prometheus
    start_http_server(METRICS_PORT)
    log.info(f"Endpoint /metrics disponible en puerto {METRICS_PORT}")

    r = connect_redis()
    generator_up.set(1)

    while True:
        try:
            order = build_order()
            r.lpush(QUEUE_NAME, json.dumps(order))
            orders_generated.labels(region=order["region"]).inc()

            log.info(
                f"Order generated: id={order['order_id'][:8]}, "
                f"region={order['region']}, items={len(order['items'])}, "
                f"total=S/{order['total_amount']:.2f}"
            )

            time.sleep(GENERATION_INTERVAL_SEC)

        except redis.exceptions.ConnectionError as e:
            log.error(f"Perdida conexion a Redis: {e}. Reconectando...")
            generator_up.set(0)
            r = connect_redis()
            generator_up.set(1)
        except Exception as e:
            log.error(f"Error inesperado: {e}", exc_info=True)
            time.sleep(GENERATION_INTERVAL_SEC)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Generator detenido por senal externa")
        sys.exit(0)
