# Solución — Sesión 4

En esta carpeta tienes `orderflow-overview.json`: el dashboard completo, con los
cinco paneles del manual **más** el panel del Ejercicio C.

Úsalo así:

- Si tu dashboard funciona, no lo copies. Compáralo. Lo que aprendiste
  construyéndolo no está en el archivo.
- Si te quedaste a medias, cópialo a `grafana/dashboards/orderflow-overview.json`
  y sigue desde ahí. Nadie debe llegar a la Sesión 5 sin dashboard.

```bash
cp docs/soluciones/orderflow-overview.json grafana/dashboards/
```

```powershell
Copy-Item docs\soluciones\orderflow-overview.json grafana\dashboards\
```

---

## Panel 6 — El ticket promedio por región

Es el panel del Ejercicio C. La consulta:

```promql
sum by (region) (rate(orderflow_order_amount_soles_total[5m]))
  /
clamp_min(sum by (region) (rate(orderflow_orders_processed_total[5m])), 0.001)
```

### Por qué se divide una tasa entre otra, y no un total entre otro

La tentación es escribir esto:

```promql
orderflow_order_amount_soles_total / orderflow_orders_processed_total
```

Y da un número. El problema es **qué** número: el ticket promedio desde que el
contenedor arrancó. Si el processor lleva tres días encendido, ese valor apenas
se mueve aunque hoy el ticket se haya duplicado. Un counter acumula desde el
principio de los tiempos y no olvida.

Con `rate(...[5m])` en los dos lados, numerador y denominador miran la **misma
ventana de cinco minutos**. El resultado es el ticket promedio *de ahora*, que es
lo que sirve para decidir algo.

### Por qué `sum by (region)` en los dos lados

Si agrupas solo el numerador, PromQL intenta casar cada serie del numerador con
una del denominador por sus etiquetas. Como no coinciden, devuelve vacío. Ambos
lados tienen que quedar con el mismo conjunto de etiquetas.

### Por qué `clamp_min`

Si en la ventana no se procesó ninguna orden en una región, el denominador vale
cero y la división da `NaN`: el panel se queda en blanco. `clamp_min` le pone un
suelo diminuto y el panel muestra cero, que es la verdad.

Es el mismo patrón del panel de tasa de error. En cuanto divides dos métricas en
PromQL, acuérdate del denominador cero: es el error más común y el más difícil de
notar, porque no falla — solo deja de dibujar.

### La unidad

El panel usa `currencyPEN`. Grafana antepone `S/` al número. Es un detalle
cosmético, pero es lo que separa un panel que alguien lee de un panel que alguien
tiene que interpretar.

---

## Antes de la Sesión 5

Comprueba que tu JSON tiene `"id": null` y `"uid": "orderflow-overview"`. Sin lo
primero el dashboard no se provisiona en otra máquina; sin lo segundo, el
validador no lo encuentra.
