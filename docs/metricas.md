# Glosario de métricas de OrderFlow

> **Este documento es la fuente de verdad.** Si una consulta PromQL de una guía,
> una diapositiva o un notebook no coincide con los nombres de esta tabla, el
> nombre correcto es el de aquí. Todo lo demás está desactualizado.

Los nombres se extraen directamente del código instrumentado:
`services/order-processor/processor.py` y `services/order-generator/generator.py`.

---

## Por qué todas empiezan con `orderflow_`

Prometheus recomienda que cada métrica lleve un prefijo que identifique a qué
aplicación o dominio pertenece. En un servidor real conviven métricas de decenas
de fuentes: el prefijo evita colisiones y permite saber de un vistazo de dónde
viene cada serie.

Nuestro prefijo es `orderflow_`. **Sin él, la consulta no devuelve nada.**

```promql
orders_processed_total             # ← no existe, devuelve vacío
orderflow_orders_processed_total   # ← correcto
```

Es el error más común del curso. Si una consulta te devuelve "Empty query result",
lo primero que debes revisar es el prefijo.

---

## Métricas del `order-processor` (puerto 8001)

| Métrica | Tipo | Etiquetas | Qué mide |
|---|---|---|---|
| `orderflow_orders_processed_total` | Counter | `region` | Órdenes procesadas y persistidas con éxito |
| `orderflow_orders_failed_total` | Counter | `reason` | Órdenes que fallaron, desglosadas por causa |
| `orderflow_processing_duration_seconds` | Histogram | — | Duración del procesamiento de una orden |
| `orderflow_queue_depth` | Gauge | — | Órdenes esperando en la cola de Redis |
| `orderflow_processor_up` | Gauge | — | `1` si el processor está activo, `0` si perdió Redis |

### Series derivadas del histograma

Un `Histogram` no es una sola serie: Prometheus genera tres familias a partir de él.
Esto confunde a casi todo el mundo la primera vez.

| Serie | Tipo | Para qué se usa |
|---|---|---|
| `orderflow_processing_duration_seconds_bucket` | Counter por cada `le` | Percentiles con `histogram_quantile()` |
| `orderflow_processing_duration_seconds_sum` | Counter | Tiempo total acumulado |
| `orderflow_processing_duration_seconds_count` | Counter | Número de observaciones |

**El sufijo `_bucket` es obligatorio en `histogram_quantile()`.** Sin él la
función no tiene los cortes que necesita y la consulta falla.

Los buckets configurados, en segundos:

```
0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0
```

El promedio se calcula dividiendo las otras dos series:

```promql
rate(orderflow_processing_duration_seconds_sum[5m])
/
rate(orderflow_processing_duration_seconds_count[5m])
```

---

## Métricas del `order-generator` (puerto 8000)

| Métrica | Tipo | Etiquetas | Qué mide |
|---|---|---|---|
| `orderflow_orders_generated_total` | Counter | `region` | Órdenes sintéticas encoladas en Redis |
| `orderflow_generator_up` | Gauge | — | `1` si el generator está activo |

---

## Valores reales de la etiqueta `reason`

Esta es la lista **completa** de valores que `orderflow_orders_failed_total`
puede tomar. No hay ningún otro. Si filtras por un valor que no está aquí, la
consulta devuelve vacío y parecerá que no hay errores.

> **Ojo: no vas a ver los diez.** En un stack sano solo aparecen los **cuatro
> fallos simulados** de la segunda tabla, repartidos más o menos por igual. Los
> de validación exigen órdenes mal formadas, y el generator siempre las produce
> correctas; los del pipeline exigen una avería real.
>
> Que solo veas cuatro es señal de que todo funciona, no de que te falte algo.

### Errores de validación (el pedido llegó mal formado)

| Valor | Se emite cuando |
|---|---|
| `missing_order_id` | La orden no trae `order_id` |
| `missing_customer_id` | La orden no trae `customer_id` |
| `empty_items` | La orden llega sin artículos |
| `invalid_total_amount` | El importe es cero o negativo |

### Fallos simulados de procesamiento

Se inyectan aleatoriamente con probabilidad `ERROR_RATE_PCT` (5 % por defecto,
configurable en `.env`).

| Valor | Representa |
|---|---|
| `postgres_timeout` | La escritura al data warehouse no respondió a tiempo |
| `validation_failed` | Fallo de validación de negocio aguas abajo |
| `duplicate_order` | La orden ya existía en el warehouse |
| `external_api_unreachable` | Un servicio externo no respondió |

### Errores del propio pipeline

| Valor | Se emite cuando |
|---|---|
| `invalid_json` | Lo que había en la cola de Redis no era JSON válido |
| `unknown` | Excepción no contemplada |

> **`db_error` no existe.** Es un valor que aparece en algunos materiales
> antiguos. Filtrar por él siempre devuelve vacío. El equivalente real es
> `postgres_timeout`.

---

## Etiquetas que añade Prometheus al scrapear

No las emite el código: las inyecta `prometheus.yml` al recoger cada target.
Sirven para agrupar sin tener que conocer los nombres de las métricas.

| Etiqueta | Valores | Definida en |
|---|---|---|
| `job` | `order-generator`, `order-processor`, `prometheus`, … | `job_name` de cada scrape config |
| `instance` | `order-processor:8001`, … | El target scrapeado |
| `service` | `generator`, `processor` | Bloque `labels:` del scrape config |
| `component` | `pipeline` | Bloque `labels:` del scrape config |

Por eso `sum by (service) (...)` funciona: `service` viene del scrape config, no
del código Python.

> **Cuidado al editar `prometheus.yml`.** Si borras el bloque `labels:` de un
> target, las consultas que agrupan por `service` dejan de funcionar sin dar
> ningún error: simplemente devuelven una serie sin esa etiqueta.

---

## Métricas de los exporters (a partir de la Sesión 2)

Las emiten los exporters, no nuestro código. **No llevan el prefijo `orderflow_`**,
porque no son nuestras: cada exporter usa el suyo.

| Origen | Prefijo | Puerto | Ejemplos |
|---|---|---|---|
| `postgres-exporter` | `pg_` | 9187 | `pg_up`, `pg_stat_database_numbackends` |
| `redis-exporter` | `redis_` | 9121 | `redis_up`, `redis_memory_used_bytes`, `redis_connected_clients` |
| Prometheus | `prometheus_` | 9090 | `prometheus_tsdb_head_series` |

Para saber qué expone realmente un exporter, no lo adivines: pregúntaselo.

```bash
curl -s http://localhost:9187/metrics | grep "^# HELP"
```

---

## Métrica instrumentada por el alumno (Sesión 2)

| Métrica | Tipo | Etiquetas | Qué mide |
|---|---|---|---|
| `orderflow_order_amount_soles_total` | Counter | `region` | Importe acumulado de las órdenes procesadas, en soles |

Se añade en la Sesión 2 como ejercicio de instrumentación. Es la única métrica
del stack que mide **negocio** en vez de infraestructura, y de ella salen dos
indicadores que no se pueden obtener de ninguna otra:

```promql
# Ingresos por segundo
rate(orderflow_order_amount_soles_total[5m])

# Ticket promedio: cociente de dos contadores
rate(orderflow_order_amount_soles_total[5m])
/
rate(orderflow_orders_processed_total[5m])
```

---

## Cómo verificar cualquier nombre en 5 segundos

Nunca confíes en la memoria ni en una diapositiva. El endpoint `/metrics` es la
verdad:

```bash
# Todas las métricas de OrderFlow con su descripción
curl -s http://localhost:8001/metrics | grep "^# HELP orderflow"

# ¿Existe esta métrica concreta?
curl -s http://localhost:8001/metrics | grep queue_depth
```

En Windows PowerShell:

```powershell
(Invoke-WebRequest http://localhost:8001/metrics).Content -split "`n" | Select-String "^# HELP orderflow"
```

Y dentro de la propia UI de Prometheus: al escribir en el campo de consulta, el
autocompletado lista los nombres reales. Si el que buscas no aparece ahí, no existe.
