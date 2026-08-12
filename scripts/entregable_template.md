# Entregable — Monitoreo y Registro con Python

**Alumno/a:** _(tu nombre)_

Una sección por sesión. Rellena la de la sesión que acabas de terminar y deja
las demás como están hasta que llegue su momento.

En cada sección presentas **un solo ejercicio**: el que aparece indicado. Los
otros ejercicios del manual los resuelves igual, pero no hace falta que los
entregues.

---

## Sesión 1 — Fundamentos y levantamiento del stack

**Ejercicio a presentar:** C — La pregunta incómoda

**Fecha:** _(YYYY-MM-DD)_

**Valores que obtuviste:**

| Métrica | Valor |
|---|---|
| `orderflow_orders_generated_total` | _(completar)_ |
| `orderflow_orders_processed_total` | _(completar)_ |

**Tu respuesta:**

_(Dos líneas: por qué difieren.)_

---

## Sesión 2 — Métricas con Prometheus y exporters

**Ejercicio a presentar:** Bloque 4 — Tu primera métrica en Python

**Fecha:** _(YYYY-MM-DD)_

**El código que escribiste** (las dos partes: la declaración y el incremento):

```python
# (pega aquí tu código)
```

**La salida de la verificación:**

```
# (pega aquí la salida de curl http://localhost:8001/metrics | grep order_amount)
```

---

## Sesión 3 — Logs con Logstash y Elasticsearch

**Ejercicio a presentar:** A — La región problemática

**Fecha:** _(YYYY-MM-DD)_

**La región con más órdenes fallidas en la última hora:** _(completar)_

**Cómo lo averiguaste:**

_(La consulta KQL que usaste, o los pasos que seguiste en Discover.)_

**Captura de la visualización:**

![region problematica](./sesion3-region.png)

---

## Sesión 4 — Visualización en Grafana y Kibana

**Ejercicio a presentar:** C — El panel de tu métrica

**Fecha:** _(YYYY-MM-DD)_

**La consulta del panel:**

```promql
# (pega aquí tu consulta)
```

**Captura del dashboard con tu panel:**

![dashboard](./sesion4-dashboard.png)

**Comprobación:** ¿volvió el dashboard después de borrarlo desde la interfaz?
_(sí / no, y qué pasó)_

---

## Sesión 5 — Alertas y notificaciones operativas

**Ejercicio a presentar:** B — La regla `SinOrdenesProcesadas`

**Fecha:** _(YYYY-MM-DD)_

**Tu regla:**

```yaml
# (pega aquí el bloque completo)
```

**Captura de la alerta en estado `firing`:**

![alerta firing](./sesion5-firing.png)

**Al parar el processor se disparan dos alertas y solo se notifica una.**
_(Dos líneas: por qué.)_

---

## Sesión 6 — Optimización e integración con Python

**Ejercicio a presentar:** C — Cerrar el ciclo

**Fecha:** _(YYYY-MM-DD)_

**El código que añadiste al notebook 4:**

```python
# (pega aquí tu ampliación)
```

**La salida del informe:**

```
# (pega aquí el informe generado)
```

**Prueba de que la notificación llegó** (`docker compose logs webhook-receiver`):

```
# (pega aquí las líneas del webhook)
```

---

## Mini proyecto

El enunciado está en `docs/mini_proyecto.md`. Se entrega aparte: tu repositorio
con tus commits, más el documento que responde a las cinco preguntas.
