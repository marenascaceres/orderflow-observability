# Manual de práctica — Sesión 1

## Fundamentos de monitoreo y levantamiento del stack

**Capítulo 1:** Observabilidad y captura de datos operativos
**Modalidad:** sincrónica online

> Este manual contiene **todo lo que vas a ejecutar** en la sesión. Las
> diapositivas explican la teoría; los comandos y las consultas salen de aquí.
> Si algo de la pantalla no coincide con este documento, manda este documento.

---

## Qué vas a construir hoy

Hoy no construyes: **verificas y exploras**. El stack ya lo levantaste con la
*Guía de Instalación* antes de esta clase. La sesión de hoy sirve para tres cosas:

1. Confirmar que tu entorno está sano.
2. Entender qué hace cada uno de los 10 servicios y cómo se conectan.
3. Ver por primera vez, con tus ojos, una métrica y un log del mismo suceso.

Al terminar serás capaz de:

- Explicar los tres pilares de la observabilidad y la diferencia entre monitoreo y observabilidad.
- Identificar qué hace cada componente del stack y en qué etapa del pipeline actúa.
- Usar los comandos de `docker compose` para inspeccionar servicios en marcha.
- Leer el endpoint `/metrics` de un servicio y ejecutar tu primera consulta en Prometheus.
- Encontrar en Kibana el log del mismo suceso que acabas de ver como métrica.

---

## Punto de partida

**Antes de esta sesión debiste completar la Guía de Instalación.** Si no la
completaste, avísale al docente ahora: sin el stack levantado no puedes seguir la
práctica.

Necesitas:

- Docker Desktop corriendo (el icono de la ballena fijo, no animado).
- El repositorio clonado y con el archivo `.env` creado.
- Los 10 servicios habiendo arrancado al menos una vez sin errores.

---

## Las tres cajas vacías

Esto es importante para entender cómo avanza el curso, y conviene que lo tengas
claro desde hoy.

Al levantar el stack arrancan **10 servicios**, pero tres de ellos están
deliberadamente **vacíos**:

| Servicio | Hoy | Se llena en |
|---|---|---|
| **Kibana** | Sin ningún Data View. No muestra nada. | Sesión 3 |
| **Grafana** | Con la fuente de datos conectada, pero sin un solo panel. | Sesión 4 |
| **Alertmanager** | Corriendo, pero sin ninguna regla que le envíe alertas. | Sesión 5 |

No están rotos. Están esperándote. Cada sesión del curso llena una de esas cajas,
y en la Sesión 2 además le añadirás al stack tres servicios nuevos.

Al final del curso pasarás de 10 a 15 servicios, y ninguno de los que hay hoy
desaparecerá. **Todo lo que construyas sigue vivo hasta la última sesión.**

---

## Bloque 1 — Verificación rápida

### Paso 1 — Levantar el stack

Desde la carpeta del proyecto:

```bash
docker compose up -d
```

Como ya descargaste las imágenes al hacer la guía de instalación, esta vez debe
tardar unos 30 segundos, no 10 minutos.

### Paso 2 — Esperar y comprobar

Espera unos 60 segundos (Elasticsearch arranca lento) y ejecuta:

```bash
docker compose ps
```

**Qué debes ver:** 10 filas. Todas con `Up` o `healthy` en la columna STATUS.
Ninguna con `Restarting` ni `Exited`.

### Paso 3 — El validador

```bash
python scripts/validate_setup.py
```

En Mac y Linux, `python3` en lugar de `python`.

**Qué debes ver:** `Todos los checks OK (12/12)`.

Si algún check falla, no sigas: consulta `docs/troubleshooting.md` o levanta la
mano. Los siguientes bloques asumen que el stack está sano.

> **Si falla "Elasticsearch: índice orderflow-logs-\*"** y todo lo demás está en
> OK, espera 30 segundos más y vuelve a correr el validador. Ese índice no existe
> hasta que el processor manda su primer log.

---

## Bloque 2 — Recorrido por el pipeline

### Paso 4 — El camino de una orden

OrderFlow simula el pipeline de datos de un e-commerce. Una orden recorre
cuatro servicios:

```
order-generator  →  Redis  →  order-processor  →  Postgres
   (la crea)       (la encola)   (la valida y procesa)  (la almacena)
```

Y en paralelo, cada servicio emite señales:

```
métricas  →  Prometheus  →  Grafana
logs      →  Logstash    →  Elasticsearch  →  Kibana
```

### Paso 5 — Ver órdenes naciendo

```bash
docker compose logs -f order-generator
```

**Qué debes ver:** líneas de texto plano como

```
orderflow-generator  | 2026-08-12 03:12:15,481 INFO - Order generated: id=8c4a2f9b, region=lima, items=3, total=S/127.50
```

Lo de la izquierda, `orderflow-generator |`, lo añade Docker para que sepas de qué
contenedor viene cada línea. No forma parte del log.

> **Fíjate en la marca de tiempo: `03:12:15,481`.** Los milisegundos van separados
> por **coma**, no por punto, y la fecha se separa de la hora con un **espacio**,
> no con una `T`. Eso significa que **no es ISO8601**. Hoy da igual; en la Sesión 3
> ese detalle va a ser la diferencia entre un pipeline que funciona y uno que
> parece funcionar.

`Ctrl+C` para salir del stream. **Esto no detiene el servicio**, solo deja de
mostrarte sus logs.

### Paso 6 — Ver órdenes procesándose

```bash
docker compose logs -f order-processor
```

**Qué debes ver:** eventos JSON estructurados, muy distintos de los anteriores:

```json
{"timestamp":"2026-08-12 03:12:15,842","level":"INFO","service":"processor","message":"Order processed","event":"order_processed","order_id":"8c4a2f9b","region":"lima","total_amount":127.5}
```

`Ctrl+C` para salir.

> **Fíjate en la diferencia.** El generator escribe texto plano; el processor
> escribe JSON. Los dos dicen cosas parecidas, pero solo el segundo se puede
> consultar por campo. En la Sesión 3 verás por qué eso lo cambia todo.

### Paso 7 — Ver órdenes almacenadas

```bash
docker compose exec postgres psql -U orderflow -d orderflow_dw -c "SELECT COUNT(*) FROM orders;"
```

**Qué debes ver:** un número mayor que cero, que crece si repites el comando.

Y para ver algunas de verdad:

```bash
docker compose exec postgres psql -U orderflow -d orderflow_dw -c "SELECT order_id, region, total_amount, processed_at FROM orders ORDER BY processed_at DESC LIMIT 5;"
```

---

## Bloque 3 — Tu primera métrica

### Paso 8 — El endpoint crudo

Antes de mirar Prometheus, mira lo que Prometheus mira. Abre en el navegador:

```
http://localhost:8001/metrics
```

**Qué debes ver:** un muro de texto plano. No es un error: así se ve una métrica
antes de que nadie la procese. Busca (`Ctrl+F`) la palabra `orderflow`.

Cada métrica tiene tres líneas:

```
# HELP orderflow_orders_processed_total Total de ordenes procesadas exitosamente
# TYPE orderflow_orders_processed_total counter
orderflow_orders_processed_total{region="lima"} 143.0
```

`HELP` es la descripción, `TYPE` es el tipo, y la tercera línea es el valor
actual para una combinación concreta de etiquetas.

> **Éste es el modelo pull de Prometheus.** El servicio no envía nada a nadie:
> se limita a publicar su estado en una página web, y Prometheus pasa a leerla
> cada 15 segundos. Si Prometheus se cae, el servicio ni se entera.

### Paso 9 — Los targets

Abre `http://localhost:9090` y ve a **Status → Targets**.

**Qué debes ver:** tres targets en verde (`UP`): `prometheus`, `order-generator`
y `order-processor`. Fíjate en la columna **Last Scrape**: nunca pasa de 15
segundos, porque ése es el `scrape_interval` configurado.

> Hoy son 3 targets. En la Sesión 2 serán 6.

### Paso 10 — Tu primera consulta

Ve a la pestaña **Graph** y escribe:

```promql
orderflow_orders_processed_total
```

Pulsa **Execute**. Debajo del campo verás dos pestañas: **Table** y **Graph**.
Sirven para cosas distintas y conviene usar las dos.

**Mira primero `Table`.** Te lista una fila por cada serie:

```
orderflow_orders_processed_total{region="lima"}       1247
orderflow_orders_processed_total{region="arequipa"}    983
orderflow_orders_processed_total{region="trujillo"}    891
orderflow_orders_processed_total{region="piura"}       634
```

Ahí se ve el concepto de golpe: **una métrica, pero una serie temporal
independiente por cada valor de la etiqueta `region`**. Es la vista que usarás
siempre que quieras saber *cuántas* series hay o *cómo se llaman*.

**Ahora pasa a `Graph`.**

**Qué debes ver:** unas líneas que solo suben. Nunca bajan. Eso es un **Counter**:
un contador acumulativo que solo se reinicia si el servicio se reinicia.

> Las líneas de las distintas regiones se parecen mucho y cuesta distinguirlas.
> Es normal: todas crecen a ritmo parecido. Para identificarlas, pasa el ratón
> por encima de la gráfica, o vuelve a `Table`.

Ahora prueba:

```promql
orderflow_queue_depth
```

**Qué debes ver:** una línea que sube y baja. Eso es un **Gauge**: una medición
instantánea.

> **El prefijo `orderflow_` es obligatorio.** Si escribes
> `orders_processed_total` sin el prefijo, Prometheus no encuentra nada y te
> devuelve "Empty query result". Lo verás pasar muchas veces en el curso: es el
> error número uno. Todos los nombres están en `docs/metricas.md`.

---

## Bloque 4 — El mismo suceso, visto como log

### Paso 11 — Crear el Data View de Kibana

**Entra directamente por esta dirección**, no por `http://localhost:5601` a secas:

```
http://localhost:5601/app/discover
```

> **Por qué así.** Si abres `localhost:5601` sin más, Kibana muestra una pantalla
> de bienvenida —*"Start by adding integrations"*— que ocupa **toda** la ventana:
> oculta el menú lateral y la barra superior. Desde ahí no puedes navegar a
> ninguna parte, y el único botón visible, **Add integrations**, lleva a Fleet,
> que no tiene nada que ver con este curso.
>
> Tus logs ya están dentro de Elasticsearch. No hay nada que integrar.
>
> Si ya te has quedado atrapado en esa pantalla, tienes dos salidas: escribir la
> dirección de arriba, o buscar el enlace pequeño de texto **"Explore on my own"**
> —mucho menos visible que el botón— que devuelve a la interfaz normal.

Una vez dentro de Discover ya verás el menú de tres rayas (**☰**) arriba a la
izquierda. De ahí en adelante puedes navegar por el menú: **Analytics → Discover**.

Kibana te dirá que no hay ningún Data View. Créalo:

1. Click en **Create data view**.
2. **Name:** `orderflow-logs`
3. **Index pattern:** `orderflow-logs-*` — debe aparecerte abajo que coincide con al menos un índice.
4. **Timestamp field:** `@timestamp`
5. **Save data view to Kibana**.

**Qué debes ver:** vuelves a Discover y aparecen logs. Si no ves ninguno,
comprueba arriba a la derecha que el rango de tiempo diga **Last 15 minutes** y
pulsa el botón **Refresh**.

### Paso 12 — Encontrar un error concreto

Ahora vas a filtrar. La barra donde se escribe es **la caja de texto más ancha de
la fila superior**, la que tiene el texto gris *"Filter your data using KQL
syntax"*. La reconoces porque está justo entre dos cosas:

- **a su izquierda**, el desplegable con el nombre de tu Data View (`orderflow-logs`);
- **a su derecha**, el selector de fechas con el icono de calendario y el botón
  **Refresh**.

```
[ orderflow-logs ▾ ]  [ Filter your data using KQL syntax ]  [ 📅 Last 15 minutes ]
    Data View                    AQUI ESCRIBES                    Rango de tiempo
```

> **«KQL» no es otro sitio: es el idioma de esa caja.** Son las siglas de
> *Kibana Query Language*, el lenguaje en que se escriben las búsquedas. Cuando
> en éste o en cualquier manual leas «escribe esta consulta KQL», significa
> siempre lo mismo: **escríbela en esa caja**. No hay una segunda barra en otro
> lado.

Haz clic dentro y escribe:

```
event: "order_failed"
```

Según escribes, Kibana te va sugiriendo: primero los nombres de campo, y después
de los dos puntos, los valores que existen de verdad. **Acepta sus sugerencias**:
es la forma más rápida de no filtrar por un campo que no existe.

Pulsa **Enter**.

**Qué debes ver:** solo las órdenes que fallaron — alrededor del 5 % de las que
había antes, porque ése es el valor de `ERROR_RATE_PCT` en tu `.env`.

Y ahora el desglose: en el **panel izquierdo**, donde está la lista de campos,
busca `reason` y haz clic en él. Se despliega un resumen con los motivos de fallo
más frecuentes y su porcentaje.

> Los valores posibles de `reason` están en `docs/metricas.md`. **`db_error` no
> existe**: si filtras por él no obtendrás nada, y no será porque no haya errores.

### Paso 13 — Unir los dos mundos

Éste es el punto de toda la sesión. Compara:

| En Prometheus | En Kibana |
|---|---|
| `orderflow_orders_failed_total` te dice **cuántas** órdenes fallaron | `event: "order_failed"` te dice **cuáles** fallaron y **por qué** |
| Sirve para alertar: "la tasa de error pasó del 10 %" | Sirve para investigar: "la orden a3f9 falló por `postgres_timeout` a las 03:47:22" |
| Barato de guardar: un número por serie | Caro de guardar: un documento por suceso |

Una métrica te dice que algo va mal. Un log te dice qué. **Necesitas los dos**, y
ése es el motivo por el que este stack tiene dos ramas.

---

## Ejercicios (haz estos tú solo)

### Ejercicio A — Cuenta las regiones

En Prometheus, ejecuta `orderflow_orders_processed_total` y anota cuántas
regiones distintas aparecen y cómo se llaman.

*Pista: hazlo desde la pestaña **Table**, no desde **Graph**. Una fila por
región.*

### Ejercicio B — Encuentra la métrica del generator

El generator también expone métricas, en el puerto 8000. Encuentra el nombre de
la métrica que cuenta las órdenes **generadas** (no las procesadas) y ejecútala
en Prometheus.

*Pista: `http://localhost:8000/metrics` y busca `# HELP`.*

> **Cuidado con las métricas que terminan en `_created`.** La librería
> `prometheus_client` añade una por cada contador, con **la misma descripción**
> que el original, así que la línea `# HELP` no sirve para distinguirlas. Lo que
> las distingue es el `# TYPE`:
>
> ```
> # TYPE orderflow_orders_generated_total    counter   <- el contador
> # TYPE orderflow_orders_generated_created  gauge     <- una marca de tiempo
> ```
>
> El valor de una `_created` es el instante en que nació la métrica, en segundos
> desde 1970 (`1.786938e+09`). No cuenta nada y nunca cambia. **Si el número que
> ves parece una cifra enorme en notación científica, te has equivocado de
> métrica.**

### Ejercicio C — La pregunta incómoda

Compara los valores de `orderflow_orders_generated_total` y
`orderflow_orders_processed_total`. ¿Son iguales? ¿Deberían serlo?

Para no sumar cinco regiones a mano, envuelve cada una en `sum()`:

```promql
sum(orderflow_orders_generated_total)
```

```promql
sum(orderflow_orders_processed_total)
```

Y mira también las que fallaron:

```promql
sum(orderflow_orders_failed_total)
```

Escribe en dos líneas por qué difieren.

> **Si al sumar procesadas + fallidas te sale MÁS que las generadas**, tu stack
> no está roto. Pasan dos cosas a la vez:
>
> 1. **Tus tres consultas no fueron simultáneas.** Entre que escribiste la
>    primera y la tercera, el generator siguió produciendo. Compruébalo pidiendo
>    las tres de golpe:
>
>    ```promql
>    sum(orderflow_orders_generated_total) - sum(orderflow_orders_processed_total) - sum(orderflow_orders_failed_total)
>    ```
>
> 2. **Prometheus tampoco scrapea los dos servicios en el mismo instante.** Cada
>    uno se lee cada 15 segundos, pero desfasados entre sí. Siempre estás
>    restando un dato de hace unos segundos menos otro de hace otros tantos.
>
> Por eso, en la Sesión 2 aprenderás que dos contadores de servicios distintos
> se comparan con `rate()` sobre la misma ventana, nunca restando acumulados.

---

## Si algo falla

| Síntoma | Causa probable | Solución |
|---|---|---|
| `docker compose ps` muestra menos de 10 filas | El stack no terminó de arrancar | Espera 60 s y repite. Si sigue, `docker compose up -d` otra vez |
| Un servicio en `Restarting` | Suele ser Elasticsearch por falta de memoria | Cierra aplicaciones; revisa `ES_JAVA_OPTS` en `.env` |
| Prometheus no muestra targets en verde | Los servicios Python aún arrancan | Espera 30 s y refresca la página de Targets |
| Una consulta devuelve "Empty query result" | Falta el prefijo `orderflow_` | Consulta `docs/metricas.md` |
| Discover en Kibana sale vacío | El rango de tiempo o el índice | Pon "Last 15 minutes" y pulsa Refresh |
| `psql` dice que no existe la tabla `orders` | Postgres se inicializó mal | `docker compose down -v` y `docker compose up -d` (borra los datos) |

Para cualquier otro problema: `docs/troubleshooting.md`.

---

## Antes de la Sesión 2

1. **Baja el stack** para liberar memoria:

   ```bash
   docker compose down
   ```

   Sin `-v`. Ese flag borraría los datos.

2. **Lee** `docs/prometheus_intro.md`. La Sesión 2 lo da por sabido.

3. **Hojea** `docs/metricas.md`. No hay que memorizarlo, pero sí saber que existe:
   lo vas a consultar en todas las sesiones que quedan.

4. **Completa el entregable** con la plantilla `scripts/entregable_template.md`.

> En la Sesión 2 vas a añadir tres servicios nuevos al stack y vas a escribir tu
> primera métrica en Python. Ven con el repositorio actualizado: te diremos el
> comando al empezar.
