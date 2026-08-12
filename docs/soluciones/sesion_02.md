# Solución — Ejercicio de instrumentación de la Sesión 2

> Intenta resolverlo antes de leer esto. El ejercicio son cuatro líneas; el
> valor está en pelearse con ellas, no en copiarlas.

---

## 1. Declarar el Counter

En `services/order-processor/processor.py`, en el bloque de métricas, donde está
el primer `TODO`:

```python
order_amount = Counter(
    "orderflow_order_amount_soles_total",
    "Importe acumulado de las ordenes procesadas, en soles",
    ["region"],
)
```

### Por qué así

- **`Counter` y no `Gauge`.** El importe acumulado solo puede crecer. Un `Gauge`
  serviría para "importe de la última orden", que no es lo que queremos.
- **El sufijo `_total`.** Convención de Prometheus para contadores. `prometheus_client`
  lo añade solo si no lo pones, pero es mejor escribirlo y saber que está ahí.
- **La unidad en el nombre.** `_soles_` evita la pregunta "¿esto son céntimos o soles?"
  dentro de seis meses. Prometheus recomienda unidades base explícitas.
- **La etiqueta `region` y ninguna más.** Podrías caer en la tentación de añadir
  `customer_id`: **no lo hagas.** Cada valor distinto de una etiqueta crea una
  serie temporal nueva. Con 4 regiones tienes 4 series; con 50.000 clientes
  tendrías 50.000, y tumbarías Prometheus. Es el error de cardinalidad que se
  explicó en la teoría.

---

## 2. Incrementarlo

En la función `process_one()`, justo después de `orders_processed`:

```python
orders_processed.labels(region=region).inc()
order_amount.labels(region=region).inc(order["total_amount"])
```

### Por qué así

- **`.inc(valor)`** — un `Counter` no solo cuenta de uno en uno: acepta cualquier
  incremento positivo. Aquí sumamos soles, no unidades.
- **Dentro del `try`, después de `persist_order()`.** Si la orden falla, no debe
  sumar importe. Colocarlo antes contaría dinero que nunca se cobró.
- **La misma etiqueta `region`** que `orders_processed`. Esto es deliberado: dos
  contadores con etiquetas idénticas se pueden dividir entre sí, y de ahí sale el
  ticket promedio.

---

## 3. Aplicar el cambio

El código Python vive dentro de una imagen. Editar el archivo no basta: hay que
reconstruir la imagen.

```bash
docker compose up -d --build order-processor
```

Tarda unos 30 segundos. Solo reconstruye ese servicio; el resto del stack sigue
en pie.

---

## 4. Verificar

Primero, que la métrica exista:

```bash
curl -s http://localhost:8001/metrics | grep order_amount
```

Debes ver algo como:

```
# HELP orderflow_order_amount_soles_total Importe acumulado de las ordenes procesadas, en soles
# TYPE orderflow_order_amount_soles_total counter
orderflow_order_amount_soles_total{region="lima"} 4271.5
```

Si no aparece nada, espera 20 segundos: hasta que no se procese la primera orden
después del reinicio, la serie no existe.

Después, en Prometheus (`http://localhost:9090`), espera un ciclo de scrape (15 s)
y ejecuta:

```promql
orderflow_order_amount_soles_total
```

---

## 5. Lo que acabas de desbloquear

Con esta métrica y la que ya existía puedes calcular dos indicadores que antes
eran imposibles:

```promql
# Ingresos por segundo
rate(orderflow_order_amount_soles_total[5m])
```

```promql
# Ticket promedio: el cociente de dos contadores
rate(orderflow_order_amount_soles_total[5m])
/
rate(orderflow_orders_processed_total[5m])
```

El segundo merece un momento de atención. Estás dividiendo **dos tasas**, no dos
totales, y eso es a propósito: el cociente de los totales acumulados te daría el
ticket promedio *desde que arrancó el servicio*, que solo se mueve a paso de
tortuga. El cociente de las tasas te da el ticket promedio **de los últimos cinco
minutos**, que sí reacciona.

Es el patrón más útil de PromQL y lo vas a repetir en las Sesiones 4, 5 y 6.

---

## Antes de la Sesión 3

Tu `processor.py` ahora difiere del repositorio oficial. Eso es normal y está
bien. En el manual de la Sesión 3, el primer paso te explica cómo sincronizarte
sin perder nada: a partir de ese tag, la métrica ya viene incluida en el repo.
