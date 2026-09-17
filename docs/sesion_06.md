# Manual de práctica — Sesión 6

## Optimización e integración con Python

**Capítulo 2:** Dashboards, alertas e integración aplicada

> Las diapositivas explican la teoría; los comandos y las consultas salen de aquí.
> Si una consulta de la pantalla no coincide con este documento, manda este documento.

---

## Qué vas a construir hoy

Hoy **dejas de mirar por pantalla**.

Grafana y Kibana son excelentes para observar. Pero un informe que se genera solo
cada mañana, un chequeo que corre en cada despliegue, o una notificación con tu
propio criterio, no se hacen con clics: se hacen con código.

El stack no crece: siguen siendo 14 servicios. Lo que cambia es quién los
consulta. Hasta hoy, tú a través de un navegador. Desde hoy, Python.

**La sesión tiene dos mitades:**

| Mitad | Qué se hace |
|---|---|
| **Primera** | Consultar el stack desde Python: las métricas de Prometheus y los logs de Elasticsearch |
| **Segunda** | **El trabajo práctico**: montar tu propio pipeline, con la API que tú elijas, y verlo aparecer en Prometheus, Elasticsearch, Grafana y Kibana |

Al terminar serás capaz de:

- Consultar la API HTTP de Prometheus con `query` y `query_range`.
- Leer y agregar logs de Elasticsearch con el cliente oficial de Python.
- **Instrumentar un programa tuyo**: que publique métricas, escriba logs
  estructurados y guarde sus datos, sin tocar la configuración del stack.
- Ver tu propio programa en las mismas pantallas donde has visto OrderFlow.

---

> **Usa Windows Terminal**, el de las pestañas, no la consola azul clásica. Ésta
> procesa las líneas según le llegan y puede desordenar un bloque pegado de
> varias. Si aparece un `>>` esperando, pulsa `Ctrl+C` y vuelve a pegar.

## Punto de partida

Necesitas los **seis archivos** que descargaste de la plataforma: los cuatro
notebooks `.ipynb`, su `requirements.txt` y `lab_pipeline.py`, que es el esqueleto
del trabajo práctico.

**Paso 1.** Crea la carpeta `notebooks/` en tu repositorio y copia dentro los
seis archivos:

**Windows (PowerShell):**
```powershell
New-Item -ItemType Directory -Force -Path notebooks | Out-Null; Copy-Item "$HOME\Downloads\*.ipynb","$HOME\Downloads\requirements.txt","$HOME\Downloads\lab_pipeline.py" notebooks\
```

**Mac/Linux:**
```bash
mkdir -p notebooks
cp ~/Downloads/*.ipynb ~/Downloads/requirements.txt ~/Downloads/lab_pipeline.py notebooks/
```

Comprueba que están los seis:

```bash
ls notebooks
```

> **Cuidado con `requirements.txt`.** Ya existen otros dos en tu repositorio, uno
> por cada servicio Python. Éste es distinto y va en `notebooks/`. Si lo copias
> encima de `services/order-processor/requirements.txt`, rompes el processor.

**Paso 2.** Levanta el stack y comprueba que `ERROR_RATE_PCT` está en `5`:

```bash
docker compose up -d
```

Si lo dejaste en 30 al final de la Sesión 5, los números de hoy van a salir en
rojo desde el principio y el informe final perderá gracia.

**Paso 3.** Instala las dependencias. Estas van en **tu** máquina, no en un
contenedor: los notebooks consultan el stack desde fuera, por `localhost`, igual
que lo haría un script en tu trabajo.

```bash
pip install -r notebooks/requirements.txt
```

**Paso 4.** Arranca JupyterLab:

```bash
jupyter lab
```

Se abre el navegador. Entra en la carpeta `notebooks/`.

---

## Dónde se escribe cada cosa

Este manual mezcla varios sitios distintos. Antes de empezar, ten claro cuál es cuál:

| Si el bloque empieza por… | Va en… |
|---|---|
| `docker`, `Invoke-WebRequest` | **PowerShell**, siempre desde la carpeta del repositorio |
| `rate(`, `sum(`, `increase(`, `count(` | **El navegador**, en `http://localhost:9090` → pestaña **Graph** |
| Texto con sangría (YAML, Python) | **VS Code**, en el archivo que se indique |
| `http://localhost:...` a secas | **El navegador** |

**Todos los comandos de Docker de este curso se escriben desde la carpeta del
repositorio.** Tu PowerShell debe mostrar algo así antes del cursor:

```
PS D:\...\orderflow-observability>
```

Si no es así, colócate ahí antes de nada:

```powershell
cd C:\ruta\donde\clonaste\orderflow-observability
```

`docker compose` no adivina qué stack quieres manejar: busca el archivo
`docker-compose.yml` **en la carpeta donde estás parado**. Desde otro sitio te
dirá que no encuentra ninguna configuración.

> **Y si un comando te responde «no se reconoce el término X»**, no está roto tu
> ordenador: ese comando es de otro idioma. `head`, `tail`, `grep` y `wc` son de
> Linux y Mac. En Windows PowerShell se dice así:
>
> | Quiero… | Linux / Mac | Windows PowerShell |
> |---|---|---|
> | Ver solo el principio | `head -20` | `Select-Object -First 20` |
> | Ver solo el final | `tail -20` | `Select-Object -Last 20` |
> | Buscar una palabra | `grep queue` | `Select-String queue` |
> | Contar líneas | `wc -l` | `Measure-Object -Line` |

---

## Bloque 1 — La API de Prometheus

Abre `01_prometheus_api.ipynb`.

**Paso 5.** Ejecuta la primera celda de código (`Shift + Enter`).

Define `prom_query()` y lanza `sum(orderflow_orders_processed_total)`. Debe
devolver una lista con un elemento, y dentro un par `[timestamp, "valor"]`.

Fíjate en un detalle que sorprende a todo el mundo la primera vez: **el valor
viene como cadena de texto**, no como número. La API lo devuelve así a propósito,
para no perder precisión en números muy grandes. Si vas a operar con él, hay que
convertirlo con `float()`.

**Paso 6.** Ejecuta la celda de la función `existe()`.

Compara dos nombres: `orderflow_orders_processed_total` y
`orders_processed_total`. El segundo devuelve `NO EXISTE`.

> **Este es el error más caro de la sesión y merece un minuto.** Cuando consultas
> una métrica que no existe, Prometheus **no da error**. Devuelve una lista
> vacía, exactamente igual que si existiera pero no tuviera datos. La consulta
> parece bien escrita y el resultado parece "todavía no hay tráfico".
>
> Se pierden tardes enteras así. La función `existe()` es tres líneas y te ahorra
> todas.

**Paso 7.** Ejecuta el resto del notebook: la consulta de rango y la gráfica.

`query_range` necesita `start`, `end` y `step`. Ese `step` es la distancia entre
puntos: con `15s` sobre una hora salen 240 puntos. Pedir `step=1s` sobre una
semana devolvería 600.000 puntos por serie y tumbaría la petición. El `step` no
es un detalle cosmético: es el coste de la consulta.

---

## Bloque 2 — Los logs desde Python

Abre `02_elasticsearch_logs.ipynb`.

**Paso 8.** Ejecuta la conexión y la búsqueda de errores.

Fíjate en `level.keyword`. Elasticsearch indexa cada campo de texto **dos veces**:
como `text`, troceado en palabras para poder buscar dentro; y como `keyword`, el
valor entero, para filtrar y agrupar de forma exacta.

Un `term` sobre `level` puede no devolver nada, porque compara el valor exacto
contra un campo que fue troceado. Sobre `level.keyword` funciona siempre. Es la
misma razón por la que Kibana te ofrece `reason.keyword` cuando quieres agrupar.

**Paso 9.** Ejecuta la agregación por nivel, y después la de `tags`.

La primera cuenta sin traerse un solo documento: `size=0`. Por la red viaja un
resumen de tres líneas en vez de mil documentos. Es la diferencia entre un script
que tarda 200 ms y uno que tarda 30 segundos.

La segunda te muestra los dos orígenes por separado: `processor` y `generator`.
Ese campo `tags` lo pusiste tú en el pipeline de Logstash de la Sesión 3, en los
`input`. Lo que estás consultando hoy es consecuencia directa de aquel archivo.

**Paso 10.** Ejecuta la celda de pandas.

---

## Bloque 3 — Dos ideas que conviene llevarse (10 minutos)

Estas dos se ven en clase con los notebooks proyectados. **Los notebooks
`03_optimizacion_promql_kql.ipynb` y `04_practica_final.ipynb` quedan para que los
recorras después con calma**: están hechos y comentados.

### Lo que cuesta una consulta

Cada combinación distinta de etiquetas es **una serie** que Prometheus guarda en
memoria para siempre, aunque reciba un solo dato. El número de series es el
producto de los valores posibles de todas las etiquetas:

```
regiones (5)  ×  estados (3)  =  15 series
regiones (5)  ×  order_id (miles)  =  miles de series
```

**La regla práctica:** una etiqueta vale si sus valores son **pocos, conocidos y
estables**. `region` sí. `customer_id` no. `order_id`, jamás.

Y lo que necesita identificar un caso concreto —el `order_id`— va en los **logs**.
Por eso está en Elasticsearch y no en Prometheus. Los dos pilares no compiten: se
reparten el trabajo según el coste.

**Las recording rules** son la otra mitad de esta idea: si una expresión es cara y
se consulta mucho, Prometheus la calcula cada 30 segundos y guarda el resultado
como métrica nueva. El panel lee un número ya hecho. Tienes el ejemplo completo en
el notebook 3.

### Una sola versión de la verdad

El notebook 4 construye un informe de salud con un veredicto: `OK`, `ATENCIÓN` o
`CRÍTICO`. Fíjate en sus umbrales: **error por encima del 10 %, p95 por encima de
1 segundo**.

Son exactamente los mismos números del panel de la Sesión 4 y de la alerta de la
Sesión 5. No es casualidad: es el punto al que lleva el curso entero.

Cuando el dashboard, la alerta y el informe miden lo mismo con los mismos
umbrales, el equipo tiene **una** versión de la verdad. Cuando cada herramienta usa
su propio criterio, llega el día en que el gráfico está verde, el correo dice que
arde y el informe de la mañana dice otra cosa. Y entonces nadie cree a ninguno.

---

## Trabajo práctico — Tu propio pipeline vigilado

Hasta ahora has vigilado un sistema que te dieron hecho. **Ahora te toca construir
uno y dejarlo vigilado**, con la API que tú elijas.

### Qué vas a montar

```
   la API que elijas
          │
          ▼
    lab_pipeline.py  ──►  Postgres        (los datos)
          │
          ├──────────────►  Pushgateway   (las métricas)  ──►  Prometheus  ──►  Grafana
          │
          └──────────────►  Logstash      (los logs)      ──►  Elasticsearch ──►  Kibana
```

Es exactamente lo que hace OrderFlow, en pequeño y con tus datos. El programa repite
un **ciclo** cada 20 segundos:

```
pedir datos a la API  →  quedarse con 3 datos de cada elemento  →  guardarlos
        →  contar lo que hizo (métricas)  →  escribir lo que le pasó (logs)
```

**Corre en tu máquina**, como los notebooks, y no hace falta tocar `docker-compose.yml`
ni la configuración de Prometheus.

**Por qué las métricas van al Pushgateway.** Prometheus pasa cada 15 segundos por una
lista fija de sitios. Tu programa arranca, trabaja y termina: Prometheus nunca sabría
dónde buscarlo. El Pushgateway es el buzón que montaste en la Sesión 2 precisamente
para esto: tu programa deja ahí sus números y Prometheus los recoge en su siguiente
ronda.

### Lo que tiene que cumplir, elijas la API que elijas

| Mínimo | Qué significa |
|---|---|
| **3 datos en Postgres** | Cada elemento que guardes lleva un identificador, un texto y un número |
| **3 métricas** | Cuánto trabajo hecho, cuántos errores y cómo fue el último ciclo |
| **3 logs** | Uno `INFO`, uno `WARNING` y uno `ERROR`, cada uno en su momento |

Esos tres mínimos no dependen de la API: **son las tres preguntas que se le hacen a
cualquier proceso**. ¿Está trabajando? ¿Está fallando? ¿Sigue vivo?

---

### Paso 1 — Elegir la API y mirarla en el navegador

Sirve cualquier API **pública, que devuelva JSON y no pida registro**, y que traiga
una **lista de elementos**. Estas cuatro están comprobadas:

| API | Dirección | Dónde está la lista | Dificultad |
|---|---|---|---|
| **Productos de prueba** | `https://dummyjson.com/products?limit=30` | dentro de `products` | Fácil: datos planos y con números |
| Criptomonedas | `https://api.coinlore.net/api/tickers/?limit=20` | dentro de `data` | Media: el precio llega como texto |
| Terremotos recientes | `https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&limit=20&orderby=time` | dentro de `features` | Media: los datos están anidados |
| Publicaciones de prueba | `https://jsonplaceholder.typicode.com/posts` | la respuesta es la lista | Fácil, pero no trae números |

**Antes de escribir código, abre la dirección en el navegador.** Es la forma de saber
qué campos tiene cada elemento.

1. Copia la dirección y pégala en la barra del navegador (Chrome o Edge).
2. Verás texto con llaves `{ }` y corchetes `[ ]`. Si se ve todo en una línea, marca la
   casilla **«Dar formato»** (*Pretty-print*) que aparece arriba.
3. Busca **la lista**: los corchetes `[` que contienen varios bloques `{ }` iguales.
4. Mira **un solo elemento** y apunta los nombres de sus campos.

Así se ve un producto de la primera API:

```json
{
  "products": [
    {
      "id": 1,
      "title": "Essence Mascara Lash Princess",
      "category": "beauty",
      "price": 9.99,
      "rating": 2.56,
      "stock": 99
    },
    { "id": 2, "title": "Eyeshadow Palette with Mirror", "price": 19.99, ... }
  ],
  "total": 194
}
```

**Cómo leerlo:**

| Lo que ves | Qué es |
|---|---|
| `"products": [ ... ]` | **La lista.** Cada `{ }` de dentro es un elemento |
| `"id": 1` | Un campo con **número** |
| `"title": "Essence..."` | Un campo con **texto**: va entre comillas |
| `"price": 9.99` | Un **número** sin comillas: sirve como valor |
| `"price": "9.99"` | Si lo vieras **con comillas**, sería texto que parece número: habría que convertirlo |

**De cada elemento necesitas tres campos:** uno que lo identifique, uno de texto y uno
numérico. En los productos: `id`, `title` y `price`.

> Si tu API tiene los datos **anidados** (un `{ }` dentro de otro), el campo se lee por
> pasos. En los terremotos, la magnitud está en `properties` → `mag`, y en Python se
> escribe `item["properties"]["mag"]`.

---

### Paso 2 — Entender el archivo, de arriba abajo

Abre `notebooks/lab_pipeline.py`. **Solo tienes que tocar cuatro huecos**, marcados con
`TODO`; todo lo demás ya funciona. Pero antes hay que entender qué hace cada parte, en
el mismo orden en que aparece.

#### 1. La cabecera y los `import`

```python
import json, os, socket, time
from datetime import datetime, timezone

import psycopg2
import requests
from prometheus_client import CollectorRegistry, Counter, Gauge, push_to_gateway
```

| Librería | Para qué |
|---|---|
| `requests` | Pedir datos a la API |
| `psycopg2` | Hablar con Postgres |
| `prometheus_client` | Crear las métricas y enviarlas al buzón. Es la misma que usa el processor de OrderFlow |
| `socket`, `json` | Enviar los logs a Logstash |
| `datetime` | Poner la hora a cada log |

#### 2. `TODO 1` — Tu nombre y tu API

```python
NOMBRE = "lab_cambia_esto"
API_URL = "https://cambia.esta.url/que/devuelve/json"
INTERVALO_S = 20
VUELTAS = 15
```

| Variable | Qué es |
|---|---|
| `NOMBRE` | Cómo se llamará tu pipeline. **Es tu etiqueta**: con ella verás solo lo tuyo en Postgres, Prometheus y Kibana, aunque toda la clase use el mismo stack. En minúsculas, sin espacios y único, por ejemplo `lab_ana` |
| `API_URL` | La dirección del Paso 1 |
| `INTERVALO_S`, `VUELTAS` | Cada cuánto repite el ciclo y cuántas veces: 15 vueltas cada 20 segundos son 5 minutos |

#### 3. Las conexiones

```python
PG = dict(host="localhost", port=5432, dbname="orderflow_dw", ...)
PUSHGATEWAY = "localhost:9091"
LOGSTASH = ("localhost", 5044)
```

Las tres van a `localhost` porque tu programa corre **fuera** de la red de Docker y
entra por los puertos que el stack publica. Un contenedor, desde dentro, los llamaría
por su nombre (`postgres`, `pushgateway`, `logstash`). No hay que tocar nada aquí.

#### 4. `TODO 2` — `extraer()`: tus tres datos

Recibe **un** elemento de la lista y devuelve los tres datos. Con los productos:

```python
def extraer(item):
    item_id = item.get("id")
    label = item.get("title")
    valor = item.get("price")

    if item_id is None or valor is None:
        return None

    return str(item_id), str(label), float(valor)
```

| Línea | Qué hace |
|---|---|
| `item.get("id")` | *«Dame el campo `id` de este elemento.»* El nombre sale de lo que viste en el navegador. Si el campo no existe, devuelve `None` en vez de romperse |
| `if ... is None: return None` | Si falta algo imprescindible, el elemento se **descarta**: el programa lo cuenta y sigue |
| `str(...)`, `float(...)` | Convierte al tipo que espera la tabla: texto, texto y número |

**Si tu API no trae ningún número**, cuenta algo: `float(len(item.get("body", "")))` es
la longitud de un texto.

**Si el número llega como texto** (`"price_usd": "76190.56"`), `float()` lo convierte.

#### 5. `TODO 3` — Las métricas

Es la parte más importante del trabajo. Mírala despacio.

**Primero, la caja donde viven:**

```python
REGISTRO = CollectorRegistry()
```

Un **registro** es la caja donde se guardan tus métricas mientras el programa corre.
Cuando llega el momento, se envía **la caja entera** al buzón. Toda métrica que crees
tiene que ir dentro de esta caja; si no, nunca sale de tu programa.

**Después, la métrica que ya está hecha, parte por parte:**

```python
items_guardados = Counter(
    "lab_items_guardados_total",        # 1. el nombre, tal como aparecerá en Prometheus
    "Elementos guardados en Postgres",  # 2. la descripción, para quien la lea
    registry=REGISTRO,                  # 3. la caja donde vive
)
```

| Parte | Qué es | Norma |
|---|---|---|
| `items_guardados` | El nombre **en tu código**. Con él la usas: `items_guardados.inc(30)` | El que quieras |
| `Counter(...)` | El **tipo** de métrica | Ver la tabla siguiente |
| `"lab_items_guardados_total"` | El nombre **en Prometheus**. Es lo que escribirás en Grafana | Empieza por `lab_`; minúsculas y guiones bajos; los contadores acaban en `_total` |
| `"Elementos guardados..."` | La descripción | Una frase corta |
| `registry=REGISTRO` | Dentro de la caja | **Obligatorio** |

**Los dos tipos que vas a usar**, los mismos de la Sesión 2:

| Tipo | Se comporta como | Se usa con | Para qué |
|---|---|---|---|
| **`Counter`** | Un cuentakilómetros: **solo sube** | `.inc()` suma 1 · `.inc(30)` suma 30 | Cosas que se acumulan: elementos guardados, errores |
| **`Gauge`** | Un velocímetro: **sube y baja** | `.set(0.87)` pone ese valor | Un estado del momento: cuánto tardó el último ciclo |

**Y dónde se usa la que ya está hecha**, dentro de `ciclo()`:

```python
if filas:
    guardar(conexion, filas)
    items_guardados.inc(len(filas))   # suma los elementos que acaba de guardar
```

**Tu trabajo: crear dos más con el mismo patrón**, y usarlas en su sitio:

```python
errores = Counter(
    "lab_errores_total",
    "Ciclos que terminaron en error",
    registry=REGISTRO,
)

ultimo_ciclo = Gauge(
    "lab_ultimo_ciclo_duracion_seconds",
    "Lo que tardo el ultimo ciclo",
    registry=REGISTRO,
)
```

| Métrica | Dónde se usa | Instrucción |
|---|---|---|
| `errores` | En el bloque de error de `ciclo()` (marcado `TODO 4 (ERROR)`) | `errores.inc()` |
| `ultimo_ciclo` | Al final de `ciclo()` (marcado `TODO 3`) | `ultimo_ciclo.set(duracion)` |

`duracion` ya está calculada en `ciclo()`: son los segundos que tardó la vuelta.

> **Cómo crear cualquier otra métrica:** elige el tipo (¿se acumula o sube y baja?),
> copia el bloque, cambia el nombre de la variable, el nombre en Prometheus y la
> descripción, deja `registry=REGISTRO`, y **úsala** en el punto del ciclo donde ocurre
> lo que mide. Una métrica creada y nunca usada aparece en Prometheus con valor 0.

#### 6. `TODO 4` — Los logs

La función `log()` ya está hecha. Se usa así:

```python
log("INFO", "ciclo_ok", guardados=30, duracion_s=0.87)
#     │        │           └── datos extra: cada uno será un campo buscable en Kibana
#     │        └── el nombre del suceso
#     └── el nivel: INFO, WARNING o ERROR
```

Tienes que escribir tres, en los tres sitios marcados con `TODO 4` dentro de `ciclo()`:

| Sitio | Nivel | Ejemplo |
|---|---|---|
| El bloque `except` (la API falló) | `ERROR` | `log("ERROR", "ciclo_fallido", motivo=type(e).__name__, detalle=str(e)[:200])` |
| `if not filas:` (no se guardó nada) | `WARNING` | `log("WARNING", "ciclo_sin_datos", recibidos=len(elementos), descartados=descartados)` |
| Al final del ciclo | `INFO` | `log("INFO", "ciclo_ok", guardados=len(filas), descartados=descartados, duracion_s=round(duracion, 3))` |

**La diferencia con un `print`:** un `print` se pierde en la pantalla; un log
estructurado se puede buscar, filtrar y contar.

#### 7. La parte resuelta: tabla, envío de logs y envío de métricas

| Pieza | Qué hace |
|---|---|
| `SQL_TABLA` | Crea la tabla `lab_items` **si no existe**. Columnas: `id`, `fetched_at` (la hora, la pone Postgres), `pipeline` (tu nombre), `item_id`, `label` y `valor` |
| `log()` | Imprime el mensaje y lo envía a Logstash en JSON, **en hora universal**. Con la hora local, tus logs aparecerían horas atrás en Kibana. Si el envío falla, avisa y sigue |
| `guardar()` | Inserta tus filas en una sola operación |
| `publicar_metricas()` | Envía la caja `REGISTRO` al buzón con la etiqueta `job` = tu `NOMBRE`. Por eso en Prometheus filtras con `{job="lab_ana"}` |
| `sacar_lista()` | Encuentra la lista dentro de la respuesta, se llame `products`, `data` o `features` |

#### 8. `ciclo()` — una vuelta, en orden

```
1. inicio = ahora
2. pedir la API        ── si falla ──►  TODO 4 (ERROR) + errores.inc()  → fin de la vuelta
3. sacar_lista()
4. extraer() de cada elemento  (los que devuelven None se cuentan como descartados)
5. guardar() + items_guardados.inc()
6. duracion = ahora - inicio
7. si no se guardó nada  ──►  TODO 4 (WARNING)
8. TODO 4 (INFO)
9. TODO 3: ultimo_ciclo.set(duracion)
10. publicar_metricas()
```

#### 9. `main()` — el arranque

Conecta con Postgres, crea la tabla, escribe el log de inicio, da las vueltas y, al
terminar o al pulsar `Ctrl+C`, escribe el log de cierre y suelta la conexión.

---

### Paso 3 — Completar y ejecutar

| # | Hueco | Tiempo |
|---|---|---|
| 1 | `NOMBRE` y `API_URL` | 5 min |
| 2 | `extraer()` | 10 min |
| 3 | Dos métricas más, y usarlas | 10 min |
| 4 | Los tres logs | 10 min |
| 5 | Ejecutar y comprobar | 10 min |

Instala lo que falta y arráncalo:

```powershell
pip install -r notebooks/requirements.txt; python notebooks/lab_pipeline.py
```

Déjalo corriendo en su pestaña. Cada vuelta imprime sus logs, por ejemplo:

```
--- vuelta 1 ---
  INFO     ciclo_ok {'guardados': 30, 'descartados': 0, 'duracion_s': 0.872}
```

---

### Paso 4 — Comprobar los tres rastros

Abre **otra pestaña**, colócate en la carpeta del repositorio y copia estos comandos.
**Cambia `lab_ana` por tu `NOMBRE`** en cada uno.

#### Comprobación 1 — Los datos, en Postgres

```powershell
docker compose exec postgres psql -U orderflow -d orderflow_dw -c "SELECT pipeline, count(*) AS filas, round(avg(valor)::numeric, 2) AS media, max(fetched_at) AS ultima FROM lab_items WHERE pipeline = 'lab_ana' GROUP BY pipeline;"
```

**Qué esperamos:** una fila con tu nombre, cuántas filas llevas, la media de `valor` y la
hora de la última. Si lo ejecutas dos veces, `filas` crece.

| Para ver… | Cambia la consulta por |
|---|---|
| Tus 5 elementos con el valor más alto | `SELECT item_id, label, valor FROM lab_items WHERE pipeline = 'lab_ana' ORDER BY valor DESC LIMIT 5;` |
| Lo guardado en cada vuelta | `SELECT date_trunc('minute', fetched_at) AS minuto, count(*) FROM lab_items WHERE pipeline = 'lab_ana' GROUP BY minuto ORDER BY minuto;` |
| Lo de toda la clase | Quita el `WHERE pipeline = ...` |

La parte que se cambia es **siempre lo que va entre comillas dobles** después de `-c`.

#### Comprobación 2 — Las métricas, en el buzón

```powershell
(Invoke-WebRequest -UseBasicParsing http://localhost:9091/metrics).Content -split "`n" | Select-String 'job="lab_ana"' | Select-String -NotMatch "_created"
```

**Qué esperamos:** tus métricas con su valor:

```
lab_errores_total{instance="",job="lab_ana"} 0
lab_items_guardados_total{instance="",job="lab_ana"} 90
lab_ultimo_ciclo_duracion_seconds{instance="",job="lab_ana"} 0.87
push_time_seconds{instance="",job="lab_ana"} 1.78e+09
```

`push_time_seconds` y `push_failure_time_seconds` los añade el buzón: son la hora del
último envío. `-NotMatch "_created"` oculta otra serie que la librería crea sola para
cada contador, con la hora en que nació.

#### Comprobación 3 — Las métricas, en Prometheus

```powershell
(Invoke-RestMethod http://localhost:9090/api/v1/query -Body @{ query = '{job="lab_ana"}' }).data.result | ForEach-Object { "{0} = {1}" -f $_.metric.__name__, $_.value[1] }
```

**Qué esperamos:** las mismas métricas. Si están en el buzón y aquí no, espera 15
segundos: aún no ha pasado la ronda.

| Para preguntar… | Cambia lo que va dentro de `query = '...'` por |
|---|---|
| Solo tu contador | `lab_items_guardados_total{job="lab_ana"}` |
| Elementos por segundo | `rate(lab_items_guardados_total{job="lab_ana"}[5m])` |
| Cuánto tardó el último ciclo | `lab_ultimo_ciclo_duracion_seconds{job="lab_ana"}` |

Es la misma consulta que escribirías en `http://localhost:9090` → **Graph**, y la misma
que irá en Grafana.

#### Comprobación 4 — Los logs, en Elasticsearch

```powershell
(Invoke-RestMethod -Method Post "http://localhost:9200/orderflow-logs-*/_search" -ContentType "application/json" -Body '{"size":0,"query":{"term":{"pipeline.keyword":"lab_ana"}},"aggs":{"niveles":{"terms":{"field":"level.keyword"}}}}').aggregations.niveles.buckets | ForEach-Object { "{0} = {1}" -f $_.key, $_.doc_count }
```

**Qué esperamos:** cuántos logs tienes de cada nivel, por ejemplo `INFO = 16`.

| Partes de la consulta | Qué hace |
|---|---|
| `"size":0` | No traer documentos, solo el recuento (Bloque 2) |
| `"term":{"pipeline.keyword":"lab_ana"}` | Solo tus logs. `.keyword` para comparar el texto entero |
| `"terms":{"field":"level.keyword"}` | Agrupar por nivel |

| Para contar… | Cambia `level.keyword` por |
|---|---|
| Por nombre de suceso | `event.keyword` |
| Por motivo de error | `motivo.keyword` (el campo que pusiste en tu log de `ERROR`) |

**Para ver un `ERROR` de verdad**, rompe algo a propósito: cambia una letra de tu
`API_URL`, deja pasar una vuelta y repite la comprobación. Es la misma idea del incidente
provocado de la Sesión 5.

---

### Paso 5 — Un gráfico en Grafana y otro en Kibana

**En Grafana** (`http://localhost:3000`): **Dashboards → New → New dashboard → Add
visualization**, datasource **Prometheus**, modo **Code**:

```promql
rate(lab_items_guardados_total{job="lab_ana"}[5m])
```

Título: `Elementos por segundo — lab_ana`. Es la misma idea del panel de throughput de
la Sesión 4: un contador no dice nada; su velocidad, sí.

**En Kibana** (`http://localhost:5601`): **Visualize Library → Create visualization →
Lens**, con el patrón `orderflow-logs-*`. En la barra de búsqueda:

```
pipeline : "lab_ana"
```

Arrastra `level.keyword` al centro. Verás cuántos `INFO`, `WARNING` y `ERROR` tienes.

> Si `pipeline` no aparece en la lista de campos, es que el patrón no se ha refrescado:
> **Stack Management → Data Views → orderflow-logs-\* → Refresh fields**.

---

### Al terminar: vacía tu buzón

```powershell
Invoke-RestMethod -Method Delete http://localhost:9091/metrics/job/lab_ana
```

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
curl -X DELETE http://localhost:9091/metrics/job/lab_ana
```

</details>

**Por qué hace falta.** Es la trampa que viste en la Sesión 2: el buzón **no olvida**. Tu
pipeline ya no corre, pero sus últimos números siguen ahí y Prometheus los seguirá
recogiendo como si fueran de ahora. Por eso, en un caso real, el proceso que usa el
buzón **borra su grupo al terminar**.

### Si algo del pipeline falla

| Síntoma | Causa probable | Solución |
|---|---|---|
| `ModuleNotFoundError: psycopg2` | Faltan dependencias | `pip install -r notebooks/requirements.txt` |
| `connection refused` al arrancar | El stack no está levantado | `docker compose up -d` |
| Guarda 0 elementos en todas las vueltas | Un nombre de campo en `extraer()` no existe | Vuelve al navegador y copia el nombre exacto |
| `TypeError` o `ValueError` en `float()` | El campo elegido no es un número | Elige otro, o cuenta algo |
| `KeyError` | Usaste `item["campo"]` con un campo que no existe | Usa `item.get("campo")` |
| Una métrica no aparece en el buzón | Le falta `registry=REGISTRO` | Añádelo |
| Una métrica aparece siempre a 0 | Se creó pero no se usa | Añade su `.inc()` o `.set()` en el ciclo |
| Las métricas no aparecen en Prometheus | Aún no ha pasado la ronda | Espera 15 segundos; mira la Comprobación 2 |
| Los logs no aparecen en Kibana | Filtro de tiempo demasiado corto, o campos sin refrescar | Amplía a «Last 1 hour»; refresca el data view |

---

## Ejercicios (para después de clase)

Los tres se hacen sobre los notebooks, con el stack levantado. Cuando termines,
comprueba la sesión entera:

```bash
python scripts/validate_sesion6.py
```

### Ejercicio A — Errores por hora

En `02_elasticsearch_logs.ipynb`, cuenta cuántos errores hubo **por hora** en las
últimas 6 horas, con una agregación `date_histogram` sobre `@timestamp`.

Después, agrupa las órdenes fallidas por su campo `reason` y compara el resultado
con lo que devuelve esta consulta en Prometheus:

```promql
topk(5, sum by (reason) (orderflow_orders_failed_total))
```

Los dos números salen de sistemas distintos y deberían contar la misma historia.
Explica en dos líneas cualquier diferencia que encuentres.

*Pista: los valores posibles de `reason` están en `docs/metricas.md`.*

### Ejercicio B — La recording rule

En `03_optimizacion_promql_kql.ipynb`, escribe completa la recording rule para el
p95 de latencia, con su nombre siguiendo la convención `nivel:metrica:operacion`,
y di qué panel de tu dashboard la usaría.

*Pista: la expresión ya la tienes en el panel 3 de la Sesión 4 y en la regla
`LatenciaAltaP95` de la Sesión 5.*

### Ejercicio C — Cerrar el ciclo

Amplía `04_practica_final.ipynb` para que:

1. Guarde el informe en `informe_salud.txt`, con fecha y hora.
2. Repita la medición cada minuto durante cinco minutos y muestre la evolución.
3. **Envíe el informe al `webhook-receiver` de la Sesión 5** cuando el veredicto
   sea `CRÍTICO`.

Con eso cierras el ciclo completo del curso: métricas y logs capturados,
consultados por código, evaluados con criterio propio, y convertidos en un aviso
que llega solo.

*El endpoint es `http://localhost:5001/alertas` y acepta un POST con JSON.
Compruébalo con `docker compose logs --tail 30 webhook-receiver`.*

---

## Si algo falla

| Síntoma | Causa probable | Solución |
|---|---|---|
| `ConnectionError` a `localhost:9090` | El stack no está levantado | `docker compose up -d` |
| Una consulta devuelve `[]` | El nombre de la métrica no existe | Úsalo con `existe()`, Paso 6 |
| `ApiError` del cliente de Elasticsearch | Versión del cliente distinta a la del servidor | `pip install "elasticsearch==8.13.*"` |
| El `term` sobre `level` no devuelve nada | Falta el sufijo `.keyword` | Paso 8 |
| `ModuleNotFoundError` | Faltan dependencias | `pip install -r notebooks/requirements.txt` |
| El veredicto sale `SIN DATOS` | El pipeline lleva poco tiempo | Deja correr 5 minutos |
| El p95 sale `None` | Falta `_bucket` o falta `sum by (le)` | Revisa la expresión |
| Jupyter no abre | El puerto 8888 está ocupado | `jupyter lab --port 8889` |

Para cualquier otro problema: `docs/troubleshooting.md`.

---

## Cierre del curso

Mira atrás un momento. En la Sesión 1 tenías tres pantallas vacías: Kibana,
Grafana y Alertmanager. Las tres están llenas, y las llenaste tú:

| Sesión | Qué añadiste |
|---|---|
| 1 | El stack en pie y la primera métrica leída con tus ojos |
| 2 | Exporters, PromQL y una métrica instrumentada por ti en Python |
| 3 | Dos orígenes de logs, estructurados y consultables |
| 4 | Un dashboard que vive como código y sobrevive a que borren el volumen |
| 5 | Alertas que avisan solas, con criterio de a quién y cuándo |
| 6 | Todo lo anterior, leído desde Python — y un pipeline tuyo, vigilado igual |

El stack pasó de 10 a 14 servicios sin que nada dejara de funcionar por el camino.
Cada sesión añadió; ninguna reemplazó.

**El mini proyecto** está en `docs/mini_proyecto.md`.
