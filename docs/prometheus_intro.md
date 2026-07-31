# Introducción a Prometheus — Lectura previa a Sesión 2

**Tiempo estimado de lectura:** 10 minutos.

Esta lectura te prepara para la Sesión 2 (Métricas con Prometheus y exporters). Cubre los 4 conceptos clave que asumiremos conocidos: **modelo pull**, **tipos de métrica**, **labels** y **PromQL básico**.

---

## 1. El modelo pull

A diferencia de sistemas como Graphite o InfluxDB (donde las apps *empujan* datos hacia el servidor), Prometheus usa un modelo **pull**: es Prometheus quien va y **scrapea** métricas desde los servicios.

Cada servicio instrumentado expone un endpoint HTTP (típicamente `/metrics`) que devuelve texto plano. Prometheus lee ese endpoint cada N segundos (por defecto 15).

Ventajas del pull:
- El servicio no necesita saber a dónde enviar métricas. Solo publica su estado.
- Se detecta fácilmente si un servicio está caído (el scraping falla).
- La configuración centralizada de scraping vive en Prometheus, no repartida en cada app.

En nuestro repo, mira `prometheus/prometheus.yml` — la sección `scrape_configs` es donde se listan los targets.

---

## 2. Los 4 tipos de métrica

Prometheus soporta cuatro tipos. Aprender la diferencia es 60% del trabajo de instrumentación.

### Counter — contador que solo crece

Representa **acumulados**: cosas que van sumando y nunca se restan. Solo se reinicia si el proceso reinicia.

**Ejemplos:**
- Total de órdenes procesadas desde que arrancó el servicio.
- Total de errores desde el último deploy.

En OrderFlow:
```python
orders_processed = Counter("orderflow_orders_processed_total", "Total de órdenes procesadas")
orders_processed.inc()  # +1
```

Convención: los counters siempre terminan en `_total`.

Para saber cuántas órdenes se procesaron **en el último minuto**, no lees el counter directamente — usas `rate()`, ver la sección PromQL.

### Gauge — valor que sube y baja

Representa un **estado actual**. Puede subir, bajar, quedarse igual.

**Ejemplos:**
- Número de conexiones abiertas en este momento.
- Órdenes esperando en la cola de Redis.
- Uso de memoria en MB.

En OrderFlow:
```python
queue_depth = Gauge("orderflow_queue_depth", "Órdenes en la cola de Redis")
queue_depth.set(42)   # valor absoluto
queue_depth.inc()     # +1
queue_depth.dec()     # -1
```

### Histogram — distribución de valores

Cuenta cuántas observaciones caen en cada rango (**bucket**). Sirve para medir **latencias, tamaños, duraciones**.

**Ejemplos:**
- Latencia de procesamiento de una orden.
- Tamaño del payload de una request.

En OrderFlow:
```python
processing_duration = Histogram(
    "orderflow_processing_duration_seconds",
    "Duración de procesamiento",
    buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0),
)
with processing_duration.time():
    procesar_orden()
```

Un histogram genera **múltiples series** en Prometheus:
- `orderflow_processing_duration_seconds_bucket{le="0.5"}` — cuántas observaciones ≤ 0.5s
- `orderflow_processing_duration_seconds_sum` — suma total de todas las observaciones
- `orderflow_processing_duration_seconds_count` — número de observaciones

Con estos datos, PromQL calcula percentiles como P50, P95, P99.

### Summary — similar a histogram

Igual propósito que histogram, pero calcula los percentiles **en el cliente** en vez de en Prometheus. En la práctica moderna se prefiere histogram porque permite agregación entre múltiples instancias. En este curso usamos histogram.

---

## 3. Labels — la dimensión clave

Los **labels** te permiten distinguir sub-poblaciones dentro de una misma métrica.

Ejemplo sin labels:
```python
orders_processed = Counter("orderflow_orders_processed_total", "Total")
```
Te da un único número global.

Ejemplo con labels:
```python
orders_processed = Counter("orderflow_orders_processed_total", "Total", ["region"])
orders_processed.labels(region="lima").inc()
orders_processed.labels(region="cusco").inc()
```
Te permite luego preguntar: "¿cuántas órdenes por región?", "¿cuál región tiene más errores?".

**Regla de oro:** los labels deben tener **cardinalidad baja** (pocas combinaciones únicas). Usar `order_id` como label es un error clásico — cada orden generaría una serie nueva, y Prometheus explota.

Labels adecuados: `region`, `service`, `endpoint`, `status_code`.
Labels PROHIBIDOS: `order_id`, `user_id`, `timestamp`, `session_id`.

---

## 4. PromQL básico

**PromQL** es el lenguaje de consultas de Prometheus. Los ejemplos usan la métrica `orderflow_orders_processed_total` de nuestro repo.

### Consultar el valor actual

```promql
orderflow_orders_processed_total
```
Te devuelve todas las series (una por combinación de labels).

### Filtrar por label

```promql
orderflow_orders_processed_total{region="lima"}
```

### Tasa de cambio — la más útil

Un counter crece, pero lo que suele importar es **la velocidad a la que crece**. `rate()` calcula la tasa por segundo en una ventana:

```promql
rate(orderflow_orders_processed_total[5m])
```
"Órdenes procesadas por segundo en los últimos 5 minutos".

Si quieres el total absoluto en la ventana (no la tasa):
```promql
increase(orderflow_orders_processed_total[5m])
```

### Agregación

```promql
sum(rate(orderflow_orders_processed_total[5m]))
```
Suma la tasa entre todas las regiones.

```promql
sum by (region) (rate(orderflow_orders_processed_total[5m]))
```
La tasa, pero agrupada por región.

### Percentiles con histogram

```promql
histogram_quantile(0.95, rate(orderflow_processing_duration_seconds_bucket[5m]))
```
"P95 de la latencia de procesamiento en los últimos 5 minutos".

Cambia `0.95` por `0.50` para P50, `0.99` para P99.

---

## Chuleta de cierre

| Necesitas...                       | Usa...             |
|------------------------------------|--------------------|
| Contar eventos acumulados          | `Counter`          |
| Medir un valor actual              | `Gauge`            |
| Medir distribución (latencia, etc) | `Histogram`        |
| Distinguir sub-poblaciones         | Labels con cardinalidad baja |
| Ver velocidad de un counter        | `rate(...[5m])`    |
| Ver totales en una ventana         | `increase(...[5m])`|
| Percentiles                        | `histogram_quantile(0.95, rate(..._bucket[5m]))` |

---

En la **Sesión 2** vas a:
- Instrumentar métricas nuevas en `order-processor` y verlas aparecer en Prometheus.
- Escribir consultas PromQL para responder preguntas de negocio.
- Configurar exporters para servicios que no son tuyos (Redis, Postgres).
- Usar Pushgateway para métricas de jobs cortos.
