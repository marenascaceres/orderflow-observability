# Manual de práctica — Sesión 2

## Métricas con Prometheus y exporters

**Capítulo 1:** Observabilidad y captura de datos operativos

> Las diapositivas explican la teoría; los comandos y las consultas salen de aquí.
> Si una consulta de la pantalla no coincide con este documento, manda este documento.

---

## Qué vas a construir hoy

Hoy el stack **crece por primera vez**: pasa de 10 a 13 servicios.

Los tres nuevos resuelven un problema concreto. Postgres y Redis no son código
nuestro: no podemos abrirlos y añadirles métricas. Necesitamos un **traductor**
que hable su idioma nativo y publique lo que ve en el formato que Prometheus
entiende. Eso es un *exporter*.

Al terminar la sesión tendrás:

1. `postgres-exporter` y `redis-exporter` publicando el estado interno de tu base de datos y tu cola.
2. `pushgateway` recibiendo métricas de scripts que viven pocos segundos.
3. Prometheus scrapeando 6 targets en lugar de 3.
4. Una métrica de negocio escrita por ti, en Python.

**Nada de lo de la Sesión 1 se toca.** Los 10 servicios que ya tenías siguen
exactamente igual. Ésta es la regla del curso: cada sesión suma, ninguna resta.

---

## Punto de partida

Antes de empezar, confirma que vienes de una Sesión 1 sana:

```bash
docker compose up -d
docker compose ps
```

**Qué debes ver:** 10 filas, todas `Up` o `healthy`.

Si algo falla aquí, resuélvelo antes de continuar. Todo lo de hoy se apoya en eso.

---

## Bloque 1 — Hacer crecer el stack

### Paso 1 — Traer los cambios de la sesión

El docente ha publicado la versión de esta sesión en el repositorio. Tráela:

```bash
git pull
```

**Qué debes ver:** una lista de archivos modificados, entre ellos
`docker-compose.yml` y `prometheus/prometheus.yml`.

> **Si `git pull` da error** porque tienes cambios locales, avisa al docente. No
> fuerces nada: se resuelve en diez segundos y es preferible no improvisar.

### Paso 2 — Mirar qué llegó, antes de ejecutarlo

Nunca levantes a ciegas algo que acabas de descargar. Mira el final de
`docker-compose.yml`:

```bash
docker compose config --services
```

**Qué debes ver:** 13 nombres. Los 10 de siempre más `postgres-exporter`,
`redis-exporter` y `pushgateway`.

Abre `docker-compose.yml` en VS Code y busca el bloque `SESION 2`. Fíjate en tres
cosas del servicio `postgres-exporter`:

- **No expone Postgres**: expone métricas *sobre* Postgres, en el puerto 9187.
- **`DATA_SOURCE_NAME`** apunta a `postgres:5432`, el nombre del servicio en la red interna de Docker. No `localhost`: dentro de un contenedor, `localhost` es él mismo.
- **Reutiliza las credenciales de `.env`.** No hay que crear ningún usuario nuevo.

### Paso 3 — Levantar solo lo nuevo

```bash
docker compose up -d
```

**Qué debes ver** — y esto es lo importante de hoy:

```
orderflow-postgres          Running
orderflow-redis             Running
...
orderflow-postgres-exporter  Created  →  Started
orderflow-redis-exporter     Created  →  Started
orderflow-pushgateway        Created  →  Started
```

Los que ya existían dicen **`Running`**: Docker los deja en paz. Solo los tres
nuevos dicen `Created`. Ése es el comportamiento incremental que vas a ver en
todas las sesiones.

```bash
docker compose ps
```

**Qué debes ver:** 13 filas.

### Paso 4 — Comprobar que los exporters hablan

```bash
curl -s http://localhost:9187/metrics | head -20
curl -s http://localhost:9121/metrics | head -20
```

En **Windows PowerShell**, `curl` no es el mismo comando. Usa:

```powershell
(Invoke-WebRequest http://localhost:9187/metrics).Content -split "`n" | Select-Object -First 20
```

O simplemente abre `http://localhost:9187/metrics` en el navegador.

**Qué debes ver:** texto plano con cientos de métricas. Muchas más de las que
emiten nuestros servicios Python, porque un exporter publica todo lo que el
servicio sabe de sí mismo.

### Paso 5 — Enseñarle los targets nuevos a Prometheus

Los exporters ya publican, pero Prometheus todavía no los lee: hay que decírselo.
Eso ya vino en el `git pull`. Míralo:

```bash
docker compose exec prometheus cat /etc/prometheus/prometheus.yml
```

Busca el bloque `SESION 2`: tres `job_name` nuevos.

Ahora hay que hacer que Prometheus relea su configuración:

```bash
docker compose restart prometheus
```

> **La forma elegante.** Reiniciar funciona, pero interrumpe el servicio. Como
> este Prometheus arranca con la opción `--web.enable-lifecycle`, se le puede
> pedir que recargue en caliente, sin perder ni un dato:
>
> ```bash
> curl -X POST http://localhost:9090/-/reload
> ```
>
> En PowerShell: `Invoke-WebRequest -Method POST http://localhost:9090/-/reload`
>
> En producción se hace así siempre. Un reinicio de Prometheus es una ventana
> ciega en tu monitoreo, justo cuando estás tocando la configuración.

### Paso 6 — Confirmar los 6 targets

Abre `http://localhost:9090` → **Status → Targets**.

**Qué debes ver:** 6 targets, todos en verde:

| Target | Puerto | Qué publica |
|---|---|---|
| `prometheus` | 9090 | Métricas del propio Prometheus |
| `order-generator` | 8000 | Órdenes generadas |
| `order-processor` | 8001 | Órdenes procesadas, latencia, cola |
| `postgres-exporter` | 9187 | Conexiones, transacciones, tamaño de la base |
| `redis-exporter` | 9121 | Memoria, clientes, comandos |
| `pushgateway` | 9091 | Lo que le empujen los scripts (ahora vacío) |

> **Si `postgres-exporter` sale en rojo**, casi siempre es la contraseña. Mira
> qué dice: `docker compose logs postgres-exporter --tail 20`.

---

## Bloque 2 — PromQL sobre lo nuevo

Todas estas consultas se escriben en `http://localhost:9090` → **Graph**.

### Paso 7 — Descubrir qué expone un exporter

No memorices nombres de métricas: pregúntale al exporter. En el campo de consulta
de Prometheus, escribe `pg_` y espera un segundo: el autocompletado te lista todo
lo que empieza así. Lo mismo con `redis_`.

Desde la terminal, la versión completa con descripciones:

```bash
curl -s http://localhost:9187/metrics | grep "^# HELP" | head -30
```

**Encuentra tú** la métrica que dice si el exporter puede hablar con Postgres.
*(Pista: es la más corta de todas y vale 1 o 0.)*

### Paso 8 — Las cuatro funciones que vas a usar todo el curso

Ejecuta estas una por una y mira la gráfica antes de pasar a la siguiente.

**`rate()` — velocidad de un contador**

```promql
rate(orderflow_orders_processed_total[5m])
```

Órdenes por segundo, promediadas sobre los últimos 5 minutos. Un contador crudo
solo sube y no dice nada útil; `rate()` es lo que lo convierte en información.

**`sum by ()` — agregar**

```promql
sum by (region) (rate(orderflow_orders_processed_total[5m]))
```

Lo mismo, pero una línea por región.

Fíjate en que `region` viene del código Python, mientras que en

```promql
sum by (service) (rate(orderflow_orders_processed_total[5m]))
```

la etiqueta `service` viene de `prometheus.yml`. Prometheus las trata igual, pero
se definen en sitios distintos.

**`increase()` — total en una ventana**

```promql
increase(orderflow_orders_failed_total[10m])
```

Cuántas órdenes fallaron en los últimos 10 minutos, desglosadas por causa.

Para quedarte solo con las tres causas principales:

```promql
topk(3, increase(orderflow_orders_failed_total[10m]))
```

**`histogram_quantile()` — percentiles**

```promql
histogram_quantile(0.95, sum(rate(orderflow_processing_duration_seconds_bucket[5m])) by (le))
```

El P95 de la latencia: el valor por debajo del cual está el 95 % de las órdenes.

> Tres cosas que fallan siempre aquí:
> 1. **El sufijo `_bucket`** es obligatorio. Sin él no hay percentil que calcular.
> 2. **`by (le)`** también. `le` es la etiqueta que marca cada corte del histograma.
> 3. **El prefijo `orderflow_`**. Sin él: "Empty query result".

### Paso 9 — Una pregunta de negocio, no de infraestructura

Éste es el patrón más valioso de PromQL: **dividir dos métricas para obtener una tercera**.

```promql
100 * sum(rate(orderflow_orders_failed_total[5m]))
/ clamp_min(
    sum(rate(orderflow_orders_processed_total[5m]))
    + sum(rate(orderflow_orders_failed_total[5m])),
    1)
```

El porcentaje de error del pipeline. Debería rondar el 5 %, que es el valor de
`ERROR_RATE_PCT` en tu `.env`.

`clamp_min(..., 1)` evita la división por cero cuando no hay tráfico. Sin él, en
un pipeline parado la consulta devolvería `NaN` y en la Sesión 5 dispararía una
alerta falsa. **Guarda este patrón**: lo vas a reutilizar tal cual.

---

## Bloque 3 — Pushgateway

### Paso 10 — El problema

Prometheus scrapea cada 15 segundos. Un script de ETL que arranca, trabaja 3
segundos y termina, nunca coincide con un scrape. Su métrica se pierde.

El Pushgateway es un buzón: el script **empuja** su métrica antes de morir, y el
buzón la conserva para que Prometheus la recoja cuando pase.

### Paso 11 — Empujar una métrica a mano

```bash
echo "orderflow_etl_registros_procesados 1500" | curl --data-binary @- http://localhost:9091/metrics/job/etl_nocturno
```

En **PowerShell**:

```powershell
Invoke-WebRequest -Method POST -Uri http://localhost:9091/metrics/job/etl_nocturno -Body "orderflow_etl_registros_procesados 1500`n"
```

Espera 15 segundos y consulta en Prometheus:

```promql
orderflow_etl_registros_procesados
```

**Qué debes ver:** el valor 1500, con la etiqueta `job="etl_nocturno"`.

Esa etiqueta `job` es la que puso tu comando, no Prometheus. Funciona porque el
scrape config lleva `honor_labels: true`. Sin esa línea, Prometheus la habría
pisado con `job="pushgateway"` y no sabrías qué script la generó.

### Paso 12 — El peligro del Pushgateway

Vuelve a consultar la métrica dentro de un minuto. **Sigue valiendo 1500.**

El Pushgateway **nunca olvida**. Si tu ETL deja de ejecutarse, la métrica se
queda congelada en su último valor para siempre, y un panel que la muestre dirá
que todo va bien mientras el proceso lleva tres días muerto.

Por eso el Pushgateway se usa **solo** para jobs de corta duración, nunca para
servicios permanentes. Para borrarla:

```bash
curl -X DELETE http://localhost:9091/metrics/job/etl_nocturno
```

---

## Bloque 4 — Tu primera métrica en Python

Hasta ahora has *configurado* métricas que ya existían. Ahora vas a *crear* una.

### Paso 13 — El problema

Todas las métricas del stack miden infraestructura: cuántas órdenes, cuánto
tardan, cuántas fallan. **Ninguna mide dinero.** Si mañana un bug hiciera que
todas las órdenes se procesaran con importe cero, tu monitoreo diría que todo
funciona perfectamente.

Vamos a arreglarlo.

### Paso 14 — Escribir la métrica

Abre `services/order-processor/processor.py` y busca `TODO (Sesion 2)`. Hay dos.

**En el primero**, en el bloque de métricas, declara un Counter llamado
`orderflow_order_amount_soles_total`, con la etiqueta `region`, que acumule el
importe de las órdenes procesadas.

**En el segundo**, dentro de `process_one()`, increméntalo con el importe de la
orden. El dato está en `order["total_amount"]`.

Pistas:

- Copia la forma de `orders_processed`, que está justo encima.
- Un `Counter` acepta incrementos de cualquier tamaño: `.inc(127.50)` es válido.
- **No añadas una etiqueta `customer_id`.** Cada valor distinto crea una serie temporal nueva; con miles de clientes tumbas Prometheus. Es el problema de cardinalidad de la teoría.

### Paso 15 — Reconstruir

El código vive dentro de una imagen: editar el archivo no basta.

```bash
docker compose up -d --build order-processor
```

**Qué debes ver:** Docker reconstruye solo ese servicio (~30 s). Los otros 12 ni
se enteran.

### Paso 16 — Verificar

```bash
curl -s http://localhost:8001/metrics | grep order_amount
```

**Qué debes ver:** tus tres líneas `# HELP`, `# TYPE` y el valor por región.
Si no aparece nada, espera 20 segundos: la serie no existe hasta que se procese
la primera orden.

Espera un ciclo de scrape y, en Prometheus:

```promql
rate(orderflow_order_amount_soles_total[5m])
```

Ingresos por segundo. Y ahora el remate:

```promql
rate(orderflow_order_amount_soles_total[5m])
/
rate(orderflow_orders_processed_total[5m])
```

**El ticket promedio de los últimos 5 minutos.** Dos métricas que escribiste tú,
divididas entre sí, produciendo un indicador de negocio que ninguna de las dos
contenía por separado.

Si te atascas, la solución comentada está en `docs/soluciones/sesion_02.md`.

---

## Ejercicios (haz estos tú solo)

### Ejercicio A — Salud de la infraestructura

Encuentra y ejecuta las métricas que responden:

1. ¿Cuántas conexiones activas tiene Postgres ahora mismo?
2. ¿Cuánta memoria está usando Redis, en bytes?
3. ¿Cuántas claves hay en la base de datos de Redis?

*No te doy los nombres. Búscalos con el autocompletado de Prometheus escribiendo
`pg_` y `redis_`, o con `curl ... | grep "^# HELP"`. Aprender a encontrar métricas
es parte del ejercicio.*

### Ejercicio B — La región más rentable

Escribe una consulta que devuelva el **ticket promedio por región** (no el global).

*Pista: la respuesta del Paso 16, pero con `sum by (region)` en el numerador y en
el denominador.*

### Ejercicio C — Cardinalidad

Ejecuta esto y anota el número:

```promql
count({__name__=~"orderflow_.*"})
```

Ahora responde en dos líneas: si añadiéramos la etiqueta `order_id` a
`orderflow_orders_processed_total`, y el sistema procesa 1 orden por segundo,
¿cuántas series temporales tendríamos al cabo de un día? ¿Es viable?

---

## Si algo falla

| Síntoma | Causa probable | Solución |
|---|---|---|
| `git pull` rechazado por cambios locales | Editaste un archivo que también cambió en el repo | Avisa al docente; no fuerces |
| `docker compose ps` muestra 10, no 13 | El `git pull` no trajo el compose nuevo | `git log --oneline -1` para ver si actualizaste |
| `postgres-exporter` en rojo en Targets | Credenciales o Postgres aún arrancando | `docker compose logs postgres-exporter --tail 20` |
| Los 3 targets nuevos no aparecen | Prometheus no releyó su configuración | `docker compose restart prometheus` |
| "Empty query result" | Falta el prefijo `orderflow_` | Consulta `docs/metricas.md` |
| `histogram_quantile` devuelve `NaN` | Falta `_bucket` o falta `by (le)` | Revisa el Paso 8 |
| Tu métrica nueva no aparece | No reconstruiste la imagen | `docker compose up -d --build order-processor` |
| `curl` no funciona en Windows | En PowerShell es otro comando | Usa `Invoke-WebRequest` o el navegador |

---

## Antes de la Sesión 3

1. **Baja el stack:** `docker compose down` (sin `-v`).
2. **Lee** `docs/logstash_intro.md` cuando el docente publique la versión de la Sesión 3.
3. **Completa el entregable** con la plantilla `scripts/entregable_template.md`.

> En la Sesión 3 los logs dejan de ser texto que pasa por la pantalla y se
> convierten en datos que se pueden consultar. Kibana deja de estar vacío.
