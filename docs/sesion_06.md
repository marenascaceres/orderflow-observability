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

Es exactamente lo que hace OrderFlow, en pequeño y con tus datos. **Corre en tu
máquina**, como los notebooks, y no hace falta tocar `docker-compose.yml` ni la
configuración de Prometheus.

**Por qué el Pushgateway y no un puerto propio.** Tu pipeline arranca, trabaja y
termina. Prometheus pasa cada 15 segundos por una lista de sitios fijos y no lo
encontraría nunca. El Pushgateway es el buzón que montaste en la Sesión 2
precisamente para esto: tu programa deja ahí sus números y Prometheus los recoge
en su siguiente ronda.

### Lo que tiene que cumplir, elijas la API que elijas

| Mínimo | Qué significa |
|---|---|
| **3 datos en Postgres** | Cada elemento que guardes lleva un identificador, un texto y un número |
| **3 métricas** | Cuánto trabajo hecho, cuántos errores y cuándo fue el último ciclo correcto |
| **3 logs** | Uno `INFO`, uno `WARNING` y uno `ERROR`, cada uno en su momento |

Esos tres mínimos no dependen de la API: **son las tres preguntas que se le hacen a
cualquier proceso**. ¿Está trabajando? ¿Está fallando? ¿Sigue vivo?

### Elegir la API

Cualquiera que sea **pública, devuelva JSON y no pida registro**. Tiene que
devolver una lista de cosas, o algo de lo que puedas sacar una lista. Algunas que
funcionan sin cuenta:

| Tema | Dirección |
|---|---|
| Publicaciones de prueba | `https://jsonplaceholder.typicode.com/posts` |
| Tiempo meteorológico | `https://api.open-meteo.com/v1/forecast?latitude=-12.05&longitude=-77.04&hourly=temperature_2m` |
| Cotizaciones de divisas | `https://open.er-api.com/v6/latest/USD` |
| Países | `https://restcountries.com/v3.1/all?fields=name,population,area` |

**Elige una que traiga un número**: precio, temperatura, población, cantidad. Si la
tuya solo trae textos, cuenta algo, por ejemplo la longitud de un campo. El
esqueleto lo explica.

### Cómo funciona el esqueleto, parte por parte

Antes de tocarlo, entiéndelo. Abre `notebooks/lab_pipeline.py`: son unas 250 líneas y
**la mitad ya está resuelta**. Esa mitad no hay que escribirla, pero sí hay que saber
qué hace, porque es donde está todo lo que has aprendido en el curso.

#### Las tres conexiones

```python
PG = dict(host="localhost", port=5432, dbname="orderflow_dw", ...)
PUSHGATEWAY = "localhost:9091"
LOGSTASH = ("localhost", 5044)
```

**Las tres van a `localhost`**, y ese detalle es el mismo de la Sesión 5 al revés: tu
pipeline corre **fuera** de la red de Docker, así que llama a los servicios por los
puertos que el stack publica. Un contenedor, desde dentro, los llamaría por su nombre
(`postgres`, `pushgateway`, `logstash`).

Las credenciales salen de las mismas variables de tu `.env`, con el valor por defecto
escrito al lado.

#### La tabla

```sql
CREATE TABLE IF NOT EXISTS lab_items (
    id          BIGSERIAL PRIMARY KEY,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    pipeline    TEXT NOT NULL,
    item_id     TEXT NOT NULL,
    label       TEXT,
    valor       DOUBLE PRECISION
)
```

| Columna | Para qué |
|---|---|
| `id` | Un número que se pone solo con cada fila |
| `fetched_at` | Cuándo se guardó. `DEFAULT now()`: lo rellena Postgres, tú no lo envías |
| `pipeline` | **Tu nombre.** Todos los de la clase escriben en la misma tabla, y esta columna es la que separa tus filas de las de los demás |
| `item_id`, `label`, `valor` | Los tres datos del hueco 2 |

**`CREATE TABLE IF NOT EXISTS`** significa «créala si no está». Por eso puedes ejecutar
el pipeline cien veces sin que falle la segunda.

#### `log()` — el envío de los registros

Es la función que usarás en el hueco 4. Hace dos cosas: imprime por pantalla y **envía
el mismo mensaje a Logstash**, en JSON, por el puerto 5044.

```python
{"timestamp": "...", "level": "INFO", "event": "ciclo_ok", "pipeline": "lab_ana", "guardados": 100}
```

| Campo | Por qué está |
|---|---|
| `timestamp` | **En hora universal (UTC)**, igual que los contenedores. Si enviaras tu hora local, Logstash la leería como universal y tus logs aparecerían en Kibana desplazadas varias horas: los buscarías en «últimos 15 minutos» y no habría nada |
| `level` | `INFO`, `WARNING` o `ERROR`. Es el campo por el que filtras y agrupas en Kibana |
| `event` | El nombre corto de lo que pasó, para poder contar cuántas veces ocurre |
| `pipeline` | Tu nombre otra vez, para ver solo lo tuyo |
| Lo que añadas tú | Cada dato extra se convierte en **un campo buscable** |

**Es el mismo formato que emite el order-processor**, y por eso Logstash lo entiende sin
tocar su configuración: el `date` que estudiaste en la Sesión 3 espera exactamente ese
formato de fecha, y tus mensajes acaban en el mismo índice `orderflow-logs-*`.

Fíjate también en que **si el envío falla, el pipeline sigue**: avisa por pantalla y no
se rompe. Un problema en el registro no debe tumbar el trabajo.

#### `publicar_metricas()` — el envío al buzón

```python
push_to_gateway(PUSHGATEWAY, job=NOMBRE, registry=REGISTRO)
```

| Pieza | Qué es |
|---|---|
| `REGISTRO` | La caja donde viven tus métricas. Se envían todas juntas |
| `job=NOMBRE` | **La etiqueta con la que aparecerán en Prometheus.** Es lo que te deja escribir `{job="lab_ana"}` y ver solo lo tuyo |
| `push_to_gateway` | Deja los valores en el buzón. Prometheus los recoge en su siguiente ronda, dentro de 15 segundos |

Se llama **al final de cada vuelta**, para que los números del buzón estén siempre al día.

#### `sacar_lista()` — la parte fea de trabajar con APIs

Unas APIs devuelven directamente una lista; otras la envuelven en un objeto con nombres
como `results`, `data` o `items`. Esta función prueba los nombres más comunes y te
devuelve la lista, venga como venga. **Así el hueco 2 es igual para todos.**

#### `ciclo()` — una vuelta completa

Es el corazón, y sigue siempre el mismo orden:

```
consultar la API  →  extraer()  →  guardar en Postgres  →  contar  →  publicar métricas
                          │
                          └─ lo que no sirve se descarta y se cuenta, no rompe nada
```

Dentro están marcados los tres sitios donde van tus logs y donde se actualizan tus
métricas. **Mide el tiempo desde el principio** (`time.perf_counter()`) para que puedas
publicar cuánto tardó.

#### `main()` — el arranque

Crea la tabla, avisa de que empieza, da las vueltas que digas y, pase lo que pase,
escribe el log de cierre y suelta la conexión. El `Ctrl+C` está contemplado: para el
pipeline sin dejar nada a medias.

> **Lo que conviene llevarse de leer este archivo:** instrumentar un programa es
> exactamente esto. Tres líneas para contar lo que hace, tres para contar lo que le pasa
> y una tabla donde dejar el resultado. No es un trabajo aparte del programa: **es parte
> de escribirlo.**

### Los cinco huecos del esqueleto

Abre `notebooks/lab_pipeline.py`. Todo está resuelto menos cinco bloques marcados
con `TODO`. Este es el reparto de los 45 minutos:

| # | Hueco | Qué hay que hacer | Tiempo |
|---|---|---|---|
| **1** | Tu API | Poner la dirección y un nombre para tu pipeline | 5 min |
| **2** | `extraer()` | Sacar de cada elemento el identificador, el texto y el número | 10 min |
| **3** | Las métricas | Añadir dos más a la que ya está | 10 min |
| **4** | Los logs | Escribir los tres, en los sitios marcados | 10 min |
| **5** | Mirarlo | Verlo en Prometheus, Elasticsearch, Grafana y Kibana | 10 min |

**Instala lo que falta y arráncalo:**

```powershell
pip install -r notebooks/requirements.txt; python notebooks/lab_pipeline.py
```

Déjalo corriendo en su propia pestaña: da vueltas cada 20 segundos e imprime lo que
va haciendo.

### Hueco 5 — Ver tu pipeline en las cuatro pantallas

**1. Tus datos, en Postgres.** Desde otra pestaña:

```powershell
docker compose exec postgres psql -U orderflow -d orderflow_dw -c "SELECT pipeline, count(*), max(fetched_at) FROM lab_items GROUP BY pipeline;"
```

**2. Tus métricas, en Prometheus.** En `http://localhost:9090` → **Graph**, escribe
el nombre de tu contador. Si tu pipeline se llama `lab_ana`:

```promql
lab_items_guardados_total{job="lab_ana"}
```

> **Si no aparece**, comprueba primero el buzón: `http://localhost:9091`. Si tus
> métricas están ahí y no en Prometheus, solo hay que esperar a la siguiente ronda.

**3. Tus logs, en Kibana.** En `http://localhost:5601/app/discover`, con el patrón
`orderflow-logs-*` que ya tienes, filtra por tu pipeline:

```
pipeline : "lab_ana"
```

Tus tres niveles tienen que aparecer en el campo `level`.

**4. Un gráfico en Grafana.** En `http://localhost:3000`, panel nuevo con el
datasource **Prometheus**, en modo **Code**:

```promql
rate(lab_items_guardados_total{job="lab_ana"}[5m])
```

Es la misma idea del panel de throughput de la Sesión 4: un contador no dice nada;
su velocidad, sí.

**5. Y un gráfico en Kibana.** Una visualización sobre `orderflow-logs-*`, filtrada
por tu pipeline y partida por `level.keyword`: cuántos INFO, cuántos WARNING y
cuántos ERROR.

> **Para ver un `ERROR` de verdad**, rompe algo a propósito: cambia una letra de la
> dirección de tu API y deja pasar una vuelta. Es la misma idea del incidente
> provocado de la Sesión 5, y es la única forma de comprobar que tu log de error
> funciona.

### Al terminar: vacía tu buzón

Cuando acabes, borra tus métricas del Pushgateway:

```powershell
Invoke-RestMethod -Method Delete http://localhost:9091/metrics/job/lab_ana
```

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
curl -X DELETE http://localhost:9091/metrics/job/lab_ana
```

</details>

**Por qué hace falta.** Es la trampa que viste en la Sesión 2: el buzón **no
olvida**. Tu pipeline ya no está corriendo, pero sus últimos números siguen ahí, y
Prometheus los seguirá recogiendo como si fueran de ahora. Un panel que los mire
seguirá en verde eternamente.

Por eso, en un caso real, el proceso que empuja al buzón **borra su grupo al
terminar**, o alguien vigila la antigüedad de lo que hay dentro.

### Si algo del pipeline falla

| Síntoma | Causa probable | Solución |
|---|---|---|
| `ModuleNotFoundError: psycopg2` | Faltan dependencias | `pip install -r notebooks/requirements.txt` |
| `connection refused` al arrancar | El stack no está levantado | `docker compose up -d` |
| `relation "lab_items" does not exist` | La tabla se crea al arrancar; el script no llegó | Mira el error anterior en la pantalla |
| Guarda 0 elementos en todas las vueltas | `extraer()` devuelve `None` siempre | Imprime un elemento y mira qué campos trae |
| `TypeError: float() argument` | El campo que elegiste como número es un texto | Elige otro campo, o cuenta algo |
| Las métricas no aparecen en Prometheus | Aún no ha pasado la ronda | Espera 15 segundos; comprueba `http://localhost:9091` |
| Los logs no aparecen en Kibana | El envío falla en silencio | El script avisa por pantalla si no pudo enviarlos |
| En Kibana sale el campo pero no filtra | Falta el sufijo `.keyword` | `level.keyword : "ERROR"` |

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
