"""
OrderFlow - Order Processor
============================
Consume ordenes desde Redis, las valida, las procesa y las persiste
en Postgres (data warehouse). Es el servicio INSTRUMENTADO del pipeline.

Emite:
  - Metricas Prometheus en el puerto 8001/metrics
    * orderflow_orders_processed_total  (counter)
    * orderflow_orders_failed_total     (counter con label reason)
    * orderflow_processing_duration_seconds (histogram)
    * orderflow_queue_depth             (gauge)
  - Logs JSON estructurados a stdout Y a Logstash (via TCP)
"""

import json
import logging
import os
import random
import socket
import sys
import time
from datetime import datetime, timezone
from logging.handlers import SocketHandler

import psycopg2
import redis
from prometheus_client import Counter, Gauge, Histogram, start_http_server
from pythonjsonlogger import jsonlogger

# ============================================================
# Configuracion desde variables de entorno
# ============================================================
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "orderflow")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "orderflow_dev_2026")
POSTGRES_DB = os.getenv("POSTGRES_DB", "orderflow_dw")

LOGSTASH_HOST = os.getenv("LOGSTASH_HOST", "logstash")
LOGSTASH_PORT = int(os.getenv("LOGSTASH_PORT", "5044"))

ERROR_RATE_PCT = float(os.getenv("ERROR_RATE_PCT", "5"))
BASE_LATENCY_MS = int(os.getenv("BASE_LATENCY_MS", "200"))
METRICS_PORT = int(os.getenv("METRICS_PORT", "8001"))

QUEUE_NAME = "orders_queue"

# ============================================================
# Logging JSON estructurado
# ============================================================
class LogstashTCPHandler(logging.Handler):
    """
    Envia cada log record a Logstash via TCP como JSON + newline.
    Si Logstash no esta disponible, silenciosamente ignora (no bloquea
    el pipeline principal).
    """

    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self._connect()

    def _connect(self) -> None:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(2.0)
            self.sock.connect((self.host, self.port))
        except Exception:
            self.sock = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if self.sock is None:
                self._connect()
            if self.sock is None:
                return
            msg = self.format(record) + "\n"
            self.sock.sendall(msg.encode("utf-8"))
        except Exception:
            # Si falla el envio, cerrar y marcar para reintentar despues
            try:
                if self.sock:
                    self.sock.close()
            except Exception:
                pass
            self.sock = None


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("processor")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "service"},
    )

    # A stdout (queda en docker logs)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    # A Logstash via TCP
    logstash_handler = LogstashTCPHandler(LOGSTASH_HOST, LOGSTASH_PORT)
    logstash_handler.setFormatter(formatter)
    logger.addHandler(logstash_handler)

    return logger


log = setup_logging()

# ============================================================
# Metricas Prometheus
# ============================================================
orders_processed = Counter(
    "orderflow_orders_processed_total",
    "Total de ordenes procesadas exitosamente",
    ["region"],
)
orders_failed = Counter(
    "orderflow_orders_failed_total",
    "Total de ordenes que fallaron durante procesamiento",
    ["reason"],
)
processing_duration = Histogram(
    "orderflow_processing_duration_seconds",
    "Duracion de procesamiento de una orden",
    buckets=(0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0),
)
queue_depth = Gauge(
    "orderflow_queue_depth",
    "Cantidad de ordenes esperando en la cola de Redis",
)
processor_up = Gauge(
    "orderflow_processor_up",
    "1 si el processor esta activo, 0 si no",
)

# ------------------------------------------------------------
# EJERCICIO DE LA SESION 2 - Instrumentar una metrica de negocio
# ------------------------------------------------------------
# Todas las metricas de arriba miden INFRAESTRUCTURA: cuantas ordenes,
# cuanto tardan, cuantas fallan. Ninguna mide NEGOCIO: cuanto dinero
# esta moviendo el pipeline.
#
# Tu tarea: declarar aqui un Counter llamado
#
#     orderflow_order_amount_soles_total
#
# con la etiqueta "region", que acumule el importe de cada orden
# procesada con exito.
#
# Un Counter puede incrementarse en cualquier cantidad, no solo de
# uno en uno: .inc(127.50) es perfectamente valido.
#
# Cuando lo declares aqui, ve a process_one() y busca el segundo TODO.
#
# La solucion completa esta en docs/soluciones/sesion_02.md, pero
# intentalo antes de mirarla.
# ------------------------------------------------------------

# TODO (Sesion 2): declara aqui el Counter orderflow_order_amount_soles_total

# ============================================================
# Conexiones
# ============================================================
def connect_redis() -> redis.Redis:
    attempt = 0
    while True:
        try:
            client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            client.ping()
            log.info("Conectado a Redis", extra={"event": "redis_connected", "host": REDIS_HOST})
            return client
        except redis.exceptions.ConnectionError as e:
            attempt += 1
            wait = min(2 ** attempt, 30)
            log.warning(
                "Redis no disponible, reintentando",
                extra={"event": "redis_retry", "attempt": attempt, "wait_sec": wait, "error": str(e)},
            )
            time.sleep(wait)


def connect_postgres():
    attempt = 0
    while True:
        try:
            conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                dbname=POSTGRES_DB,
            )
            conn.autocommit = True
            log.info("Conectado a Postgres", extra={"event": "postgres_connected", "host": POSTGRES_HOST})
            return conn
        except psycopg2.OperationalError as e:
            attempt += 1
            wait = min(2 ** attempt, 30)
            log.warning(
                "Postgres no disponible, reintentando",
                extra={"event": "postgres_retry", "attempt": attempt, "wait_sec": wait, "error": str(e)},
            )
            time.sleep(wait)


# ============================================================
# Logica de procesamiento
# ============================================================
def validate_order(order: dict) -> None:
    """Valida la estructura minima. Lanza ValueError si falla."""
    if not order.get("order_id"):
        raise ValueError("missing_order_id")
    if not order.get("customer_id"):
        raise ValueError("missing_customer_id")
    if not order.get("items"):
        raise ValueError("empty_items")
    if order.get("total_amount", 0) <= 0:
        raise ValueError("invalid_total_amount")


def simulate_processing_delay() -> float:
    """Simula latencia realista con distribucion tipo pareto."""
    base = BASE_LATENCY_MS / 1000.0
    jitter = random.paretovariate(2.5) * 0.15
    delay = base + jitter
    time.sleep(delay)
    return delay


def maybe_inject_failure() -> None:
    """Con probabilidad ERROR_RATE_PCT, lanza un error simulado."""
    if random.random() * 100 < ERROR_RATE_PCT:
        reasons = [
            "postgres_timeout",
            "validation_failed",
            "duplicate_order",
            "external_api_unreachable",
        ]
        raise RuntimeError(random.choice(reasons))


def persist_order(pg_conn, order: dict) -> None:
    """Inserta la orden en la tabla orders del DW."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO orders (order_id, customer_id, region, total_amount, currency, items_count, created_at, processed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (order_id) DO NOTHING
            """,
            (
                order["order_id"],
                order["customer_id"],
                order["region"],
                order["total_amount"],
                order.get("currency", "PEN"),
                len(order["items"]),
                order["created_at"],
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def process_one(pg_conn, order: dict) -> None:
    """Procesa una orden completa. Emite metricas y logs."""
    order_id = order.get("order_id", "unknown")
    region = order.get("region", "unknown")

    with processing_duration.time():
        try:
            validate_order(order)
            simulate_processing_delay()
            maybe_inject_failure()
            persist_order(pg_conn, order)

            orders_processed.labels(region=region).inc()

            # TODO (Sesion 2): incrementa aqui tu Counter de importe.
            # El monto de la orden esta en order["total_amount"].
            # Recuerda que .inc() acepta un argumento numerico.

            log.info(
                "Order processed",
                extra={
                    "event": "order_processed",
                    "order_id": order_id,
                    "region": region,
                    "total_amount": order.get("total_amount"),
                    "items_count": len(order.get("items", [])),
                },
            )

        except ValueError as e:
            reason = str(e)
            orders_failed.labels(reason=reason).inc()
            log.warning(
                "Order validation failed",
                extra={"event": "order_failed", "order_id": order_id, "reason": reason},
            )
        except RuntimeError as e:
            reason = str(e)
            orders_failed.labels(reason=reason).inc()
            log.error(
                "Order processing failed",
                extra={"event": "order_failed", "order_id": order_id, "reason": reason},
            )
        except Exception as e:
            orders_failed.labels(reason="unknown").inc()
            log.error(
                "Unexpected error processing order",
                extra={"event": "order_failed", "order_id": order_id, "error": str(e)},
                exc_info=True,
            )


def poll_queue_depth(r: redis.Redis) -> None:
    """Cada N iteraciones actualiza el gauge de profundidad de cola."""
    try:
        depth = r.llen(QUEUE_NAME)
        queue_depth.set(depth)
    except Exception:
        pass


# ============================================================
# Main loop
# ============================================================
def main() -> None:
    log.info(
        "Iniciando order-processor",
        extra={
            "event": "startup",
            "error_rate_pct": ERROR_RATE_PCT,
            "base_latency_ms": BASE_LATENCY_MS,
            "metrics_port": METRICS_PORT,
        },
    )

    start_http_server(METRICS_PORT)
    log.info("Endpoint /metrics disponible", extra={"event": "metrics_up", "port": METRICS_PORT})

    r = connect_redis()
    pg_conn = connect_postgres()
    processor_up.set(1)

    iteration = 0
    while True:
        try:
            iteration += 1
            if iteration % 10 == 0:
                poll_queue_depth(r)

            # BRPOP con timeout de 5s para no bloquear indefinidamente
            result = r.brpop(QUEUE_NAME, timeout=5)
            if result is None:
                continue

            _queue, raw = result
            try:
                order = json.loads(raw)
            except json.JSONDecodeError as e:
                orders_failed.labels(reason="invalid_json").inc()
                log.error("JSON invalido en cola", extra={"event": "invalid_json", "error": str(e)})
                continue

            process_one(pg_conn, order)

        except redis.exceptions.ConnectionError as e:
            log.error("Perdida conexion a Redis", extra={"event": "redis_lost", "error": str(e)})
            processor_up.set(0)
            r = connect_redis()
            processor_up.set(1)
        except psycopg2.OperationalError as e:
            log.error("Perdida conexion a Postgres", extra={"event": "postgres_lost", "error": str(e)})
            try:
                pg_conn.close()
            except Exception:
                pass
            pg_conn = connect_postgres()
        except Exception as e:
            log.error("Error en loop principal", extra={"event": "main_loop_error", "error": str(e)}, exc_info=True)
            time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Processor detenido por senal externa", extra={"event": "shutdown"})
        sys.exit(0)
