# Manual de práctica — Sesión 4

## Visualización en Grafana y Kibana

**Capítulo 2:** Dashboards, alertas e integración aplicada

> Las diapositivas explican la teoría; los comandos y las consultas salen de aquí.
> Si una consulta de la pantalla no coincide con este documento, manda este documento.

---

## Qué vas a construir hoy

Hoy **se llena la segunda caja vacía**: Grafana.

El stack sigue teniendo 13 servicios. No añadimos ninguno. Lo que cambia es que
Grafana deja de ser una pantalla en blanco y pasa a mostrar los cinco números que
resumen si OrderFlow está sano.

Y hay un segundo objetivo, menos visible pero más importante: al final de la
sesión tu dashboard **no vivirá dentro de Grafana**. Vivirá como un archivo en tu
repositorio. Esa diferencia es la que separa un dashboard que sobrevive a un
`docker compose down` de uno que se pierde.

Al terminar serás capaz de:

- Construir paneles de tipo *time series*, *stat* y *gauge* a partir de consultas PromQL.
- Definir una variable de dashboard y usarla para filtrar varios paneles a la vez.
- Exportar un dashboard a JSON y provisionarlo desde archivo.
- Convertir campos de logs en visualizaciones de Kibana y agruparlas en un dashboard.

---

## Punto de partida

Necesitas el stack de la Sesión 3 funcionando: 13 servicios, con métricas en
Prometheus y logs en Elasticsearch.

```powershell
docker compose up -d; docker compose ps --format "{{.Name}}" | Measure-Object -Line
```

**Tienen que salir 13.** Y si salen menos, **no sigas**: falta algún servicio en tu
`docker-compose.yml`, probablemente por un bloque mal pegado en una sesión anterior.

> **Por qué insistimos tanto en ese número.** Un servicio de menos **no da ningún
> error hoy**: los contenedores que ya estaban en marcha siguen funcionando por su
> cuenta —Docker los llama *huérfanos* y a veces lo menciona de pasada— y todo
> parece normal. El síntoma aparece dos sesiones después, en forma de panel vacío
> que nadie sabe explicar.

Hoy no descargas nada. Los tres cambios de configuración de esta sesión los
escribes tú, y son cortos.

### Paso 1 — Crear la carpeta de los dashboards

Ahora mismo no existe. Créala en la raíz de tu repositorio:

**Windows (PowerShell):**
```powershell
New-Item -ItemType Directory -Force -Path grafana\dashboards
```

**Mac/Linux:**
```bash
mkdir -p grafana/dashboards
```

Aquí es donde vivirá tu dashboard al final de la sesión.

### Paso 2 — Fijar el `uid` de los datasources

> 📄 **Archivo de este paso:** `grafana/provisioning/datasources/datasources.yml`

Ábrelo. Verás dos datasources declarados, `Prometheus` y `Elasticsearch`.

> **Ojo, que los tres pasos siguientes tocan tres archivos distintos**, y dos de
> ellos tienen nombres casi idénticos y viven en carpetas hermanas. Antes de pegar
> nada, comprueba en qué archivo estás.

**En el primero**, justo debajo de `type: prometheus`, añade:

```yaml
    # El uid se fija a mano a proposito. Si se omite, Grafana genera uno
    # aleatorio en cada instalacion, y los dashboards versionados en el
    # repo (Sesion 4) no encontrarian su origen de datos: cada panel
    # mostraria "Datasource not found". Con el uid fijo, el mismo JSON
    # funciona en la maquina de cualquier alumno.
    uid: prometheus
```

**En el segundo**, justo debajo de `type: elasticsearch`, añade:

```yaml
    uid: elasticsearch
```

### Paso 3 — Declarar el provider de dashboards

> 📄 **Archivo de este paso:** `grafana/provisioning/dashboards/dashboards.yml`
> — ojo, **no** es el mismo del paso anterior: aquel era `datasources`, éste es
> `dashboards`.

Hoy dice:

```yaml
providers: []
```

Esa línea vacía es la razón de que Grafana lleve tres sesiones sin un solo panel.
**Bórrala** y pon esto en su lugar:

```yaml
providers:
  - name: orderflow
    orgId: 1
    # Carpeta que veras en el menu Dashboards de Grafana.
    folder: OrderFlow
    type: file
    # false = si alguien borra el JSON de la carpeta, Grafana borra
    # tambien el dashboard. Lo dejamos en false para que el estado de
    # Grafana siempre refleje el contenido del repo.
    disableDeletion: false
    # Cada 30s relee la carpeta. Editas el JSON, guardas, refrescas
    # el navegador y ves el cambio: no hace falta reiniciar Grafana.
    updateIntervalSeconds: 30
    options:
      # Ruta de DENTRO del contenedor, donde docker-compose.yml montara
      # tu carpeta ./grafana/dashboards en el paso siguiente.
      #
      # Fijate en que va AL LADO de "provisioning", no dentro: ese otro
      # volumen esta montado en solo lectura, y Docker no puede crear un
      # punto de montaje dentro de algo que no puede escribir.
      path: /etc/grafana/dashboards
      foldersFromFilesStructure: false
```

### Paso 4 — Montar la carpeta dentro de Grafana

> 📄 **Archivo de este paso:** `docker-compose.yml`, en la raíz del repositorio.

Grafana todavía no puede ver tu carpeta `grafana/dashboards/`: está fuera del
contenedor. Un contenedor es una caja cerrada con su propio sistema de archivos, y
no ve tu disco. Para que lo vea hay que abrirle una ventana, y eso es un *volumen*.

Busca el servicio `grafana` y su sección `volumes:`:

```yaml
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
```

Antes de escribir nada, lee una de las que ya están, porque su forma lo explica
todo:

```
      - ./grafana/provisioning : /etc/grafana/provisioning : ro
          └── tu disco ───┘      └── dentro del contenedor ─┘  └ solo lectura
```

Tres partes separadas por dos puntos: qué carpeta tuya, dónde aparece dentro de la
caja, y con qué permisos.

Añade una tercera línea debajo, con la misma sangría:

```yaml
      # Sesion 4: los dashboards viven versionados en el repo. El provider
      # "orderflow" de grafana/provisioning/dashboards/dashboards.yml lee
      # de esta ruta de dentro del contenedor.
      - ./grafana/dashboards:/etc/grafana/dashboards:ro
```

La parte derecha es **exactamente** la ruta que escribiste en el Paso 3. Ahí se
cierra el circuito.

> **Por qué no cuelga de `/etc/grafana/provisioning/...`**, que sería lo intuitivo:
> ese destino está **dentro** del volumen anterior, que se monta en solo lectura.
> Para crear ahí el punto de montaje, Docker tendría que escribir en una zona
> precintada, y **Grafana no arranca**:
>
> ```
> error mounting ... create mountpoint ...: read-only file system
> ```
>
> Como las dos rutas son ahora simétricas —`grafana/dashboards` fuera,
> `/etc/grafana/dashboards` dentro— también es más fácil de recordar.

**Comprueba que los dos extremos coinciden** antes de levantar nada:

```powershell
Select-String "etc/grafana/dashboards" .\docker-compose.yml, .\grafana\provisioning\dashboards\dashboards.yml
```

Deben salir **dos** líneas, una de cada archivo. Si sale una sola, falta un extremo
del pasadizo.

### Paso 5 — Levantar y comprobar

```bash
docker compose up -d
```

Fíjate en la salida. Doce servicios dirán `Running`; **Grafana dirá `Recreated`**.
Es el único que cambió: tiene un volumen nuevo. Los demás ni se enteran.

```bash
docker compose logs grafana --tail 20
```

**Lo que confirma que ha ido bien** son estas dos líneas seguidas, sin nada entre
ellas:

```
level=info msg="starting to provision dashboards"
level=info msg="finished to provision dashboards"
```

> **Tres `level=error` que salen siempre y son inofensivos.** Grafana busca cinco
> carpetas de provisioning y tú solo tienes dos:
>
> ```
> Failed to read plugin provisioning files    path=.../plugins
> Can't read alert notification provisioning  path=.../notifiers
> can't read alerting provisioning files      path=.../alerting
> ```
>
> Las otras tres son **opcionales**, pero las reporta como error igualmente. Es el
> vecino que pasa lista de las cinco llaves del portal y anuncia que falta la del
> trastero, aunque tú no tengas trastero.
>
> Detalle para dentro de dos semanas: **el de `alerting` desaparecerá en la Sesión
> 5**, cuando crees esa carpeta.

> **Si Grafana no dice `Recreated`**, es que el cambio del `docker-compose.yml` no
> se guardó. Sin ese volumen, el resto de la sesión no funciona.

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

## Cómo pegar los bloques de código sin romperlos

Hay **dos** problemas distintos al pegar, y conviene no confundirlos: uno ocurre
en la terminal y el otro en el editor.

### En la terminal: las líneas se desordenan

> **Usa Windows Terminal**, el de las pestañas, no la consola azul clásica. Ésta
> procesa las líneas según le llegan y puede desordenar un bloque pegado de
> varias. Si aparece un `>>` esperando, pulsa `Ctrl+C` y vuelve a pegar.

### En el editor: se pierde la sangría

Varios pasos de hoy te piden pegar bloques largos en archivos. **Al copiarlos
desde el documento de Word, los espacios del principio de cada línea se
pierden.** Y esos espacios no son decoración: son lo único que indica qué
pertenece a qué.

Piensa en una lista de la compra:

```
FRUTAS:
    manzanas
    peras
```

Lo que hace que «manzanas» sea una fruta es que está **escrita más a la derecha**
que FRUTAS. Si la pegas pegada al margen, deja de ser una fruta y se convierte en
una sección nueva.

**Después de pegar cualquier bloque, comprueba esto:**

1. Mira la barra azul de abajo a la derecha de VS Code. Debe decir `Spaces: 2`.
   Si dice otra cosa, haz clic ahí → *Indent Using Spaces* → **2**.
2. Compara la primera línea que pegaste con la línea equivalente que ya existía
   más arriba. **Tienen que empezar en la misma columna.**
3. Si tu bloque quedó más a la izquierda: selecciónalo entero (clic en el número
   de la primera línea, `Shift` + clic en el de la última) y pulsa **`Tab`** una
   vez. Se desplaza todo de golpe.

`Shift+Tab` lo desplaza en sentido contrario, y `Ctrl+Z` deshace. No hay forma de
romper nada de manera irreversible.

---

## Bloque 1 — Grafana ya tiene los datos conectados

**Paso 6.** Abre `http://localhost:3000`. Usuario `admin`, contraseña `admin`.

> ⚠️ **Grafana te va a pedir que cambies la contraseña**, porque `admin` es la de
> fábrica. Tienes dos opciones y las dos valen:
>
> - Pulsar **`Skip`** (el enlace pequeño de debajo del formulario) y seguir con
>   `admin`.
> - Cambiarla — y entonces **anótala**.
>
> **Si la cambias, apúntala en algún sitio.** No es solo para entrar a la web: la
> vas a necesitar hoy mismo en el validador del Paso 24, y en la **Sesión 6**, donde
> vas a consultar Grafana desde Python. Un `401 Unauthorized` dentro de un notebook
> es de las cosas más difíciles de relacionar con un clic que diste dos semanas
> antes.
>
> **Si te quedaste sin ella**, se restablece sin perder nada —ni dashboards ni
> datasources:
>
> ```powershell
> docker compose exec grafana grafana cli admin reset-admin-password admin
> ```

**Paso 7.** Ve a **Connections → Data sources**. Verás dos, ya configurados:

- **Prometheus**, apuntando a `http://prometheus:9090`
- **Elasticsearch**, apuntando a `http://elasticsearch:9200`

Nadie los configuró a mano. Estaban en `grafana/provisioning/datasources/datasources.yml`
desde la Sesión 1. Esto es *provisioning*: configuración que llega como archivo, no
como clics.

Pulsa **Prometheus** y fíjate en la URL de tu navegador. Termina en
`/datasources/edit/prometheus`. Ese `prometheus` final es el **uid**, y es el que
acabas de fijar tú en el Paso 2.

> **Por qué importa el uid.** Un dashboard guardado en JSON no dice "usa
> Prometheus"; dice "usa el datasource con uid `prometheus`". Si Grafana genera
> ese uid al azar en cada instalación —que es lo que hacía hasta hoy—, el mismo
> JSON funcionaría en tu máquina y fallaría en la de tu compañero, con un
> *Datasource not found* en cada panel. Fijarlo a mano es lo que hace el
> dashboard portable.

**Paso 8.** Ve a **Explore** (el icono de la brújula, en la barra lateral), elige
el datasource **Prometheus** y ejecuta:

```promql
orderflow_orders_processed_total
```

> 🔑 **Antes de escribir nada: pulsa `Code`.** La zona de consulta tiene dos
> botones a la derecha, **Builder** y **Code**, y Grafana abre siempre en *Builder*
> — un formulario de desplegables donde no hay dónde teclear.
>
> Todas las consultas de este manual están escritas, así que **este manual se sigue
> siempre en modo `Code`**. Vale para Explore y para cada panel que construyas hoy.

Es la misma consulta de la Sesión 1, pero aquí no hay que salir a otra herramienta.
Explore es para investigar; los dashboards son para vigilar.

---

## Bloque 2 — Los cuatro paneles de negocio

**Paso 9.** **Dashboards → New → New dashboard → Add visualization**. Elige el
datasource **Prometheus**.

Cada panel se construye igual: escribes la consulta abajo (en modo **Code**), eliges
el tipo de visualización arriba a la derecha, ajustas las opciones del panel y
pulsas **Save dashboard** (o **Back to dashboard** para seguir añadiendo).

> ⚠️ **La primera vez que guardes, hazlo así, y no de otra forma:**
>
> | Campo | Valor |
> |---|---|
> | **Folder** | `General` |
> | **Dashboard name** | `OrderFlow — Overview (borrador)` |
>
> **Por qué no en la carpeta `OrderFlow`**, que es la que te ofrece Grafana y la que
> parece lógica: esa carpeta la creó tu propio provider en el Paso 3, y a partir del
> Paso 15 va a recibir el dashboard **provisionado desde archivo**. Si guardas ahí
> uno con el mismo título, los dos chocan — y Grafana resuelve el choque **sin decir
> nada**: o no carga el del archivo, o lo carga y **se lleva por delante el tuyo**.
>
> Con carpeta y nombre distintos no hay choque, y en el Paso 17 podrás ver los dos a
> la vez y comparar.
>
> (Si pruebas a llamarlo `OrderFlow`, a secas, Grafana lo rechaza: no admite que un
> dashboard se llame igual que su carpeta.)

### Panel 1 — Throughput

- **Consulta:**

  ```promql
  rate(orderflow_orders_processed_total[1m])
  ```

- **Tipo:** Time series
- **Título:** `Throughput (órdenes/seg)`
- **Legend → Legend format:** `{{region}}`
- **Legend → Mode:** `Table` · **Values:** marca `Last *`
- **Standard options → Unit:** `requests/sec (rps)`

> **Ese `Last *` es lo que convierte una gráfica en un panel que se puede
> vigilar.** Una serie temporal dibuja la evolución, pero no enseña ninguna cifra:
> para leer un valor habría que pasar el ratón por encima. Con esta opción, debajo
> de la gráfica aparece cada región con su último valor.
>
> El asterisco significa «el último valor que no esté vacío», y evita que el panel
> parpadee en blanco cuando una muestra aún no ha llegado.

Un counter solo sabe crecer. Graficarlo crudo dibuja una rampa que sube siempre y
no dice nada. `rate()` lo convierte en velocidad: órdenes por segundo. Eso sí se
puede leer de un vistazo.

### Panel 2 — Tasa de error

**Back to dashboard → Add → Visualization.**

- **Consulta:**

  ```promql
  sum(rate(orderflow_orders_failed_total[5m]))
    /
  clamp_min(
    sum(rate(orderflow_orders_processed_total[5m]))
    + sum(rate(orderflow_orders_failed_total[5m])),
    0.001
  ) * 100
  ```

- **Tipo:** Stat
- **Título:** `Tasa de error %`
- **Standard options → Unit:** `Percent (0-100)`
- **Thresholds:** verde por defecto, amarillo en `5`, rojo en `15`

Fíjate en el `clamp_min(...)`. El denominador es la suma de las dos tasas; si en
algún momento el processor está parado, esa suma vale cero y la división devuelve
`NaN`: el panel se queda en blanco justo cuando más te interesa mirarlo.
`clamp_min` le pone un suelo mínimo al denominador para que eso no ocurra.

Los umbrales que acabas de poner no son decorativos. En la Sesión 5 el mismo `15`
va a ser el umbral de una alerta que te escribe un correo.

> **Tu panel no va a marcar 5 %, y está bien.** El sistema falla uno de cada veinte
> pedidos, pero este panel mira **los últimos cinco minutos**: unos 300 pedidos, de
> los que fallan unos 15. Que salgan 7 o que salgan 22 es puro azar, así que verás
> el número **bailar entre el 2 % y el 8 %**. El 5 % solo aparece limpio al mirar
> una hora entera.
>
> Compruébalo tú mismo en **Explore**, con `increase` sobre una hora:
>
> ```promql
> sum(increase(orderflow_orders_failed_total[1h])) / (sum(increase(orderflow_orders_processed_total[1h])) + sum(increase(orderflow_orders_failed_total[1h]))) * 100
> ```
>
> **Y la ventana corta no es un error, es una decisión.** Un panel de vigilancia
> tiene que reaccionar deprisa: si usara una hora, un incidente tardaría media hora
> en verse. Se acepta que el número esté nervioso a cambio de que avise pronto. Para
> un informe mensual elegirías lo contrario.

### Panel 3 — Latencia P95

- **Consulta:**

  ```promql
  histogram_quantile(0.95, sum by (le) (rate(orderflow_processing_duration_seconds_bucket[5m])))
  ```

- **Tipo:** Time series
- **Título:** `Latencia P95 (seg)`
- **Legend → Mode:** `Table` · **Values:** marca `Last *`
- **Standard options → Unit:** `seconds (s)`

> **Fíjate en lo que hace la unidad.** El valor real es algo como `0.712`, y
> Grafana te lo enseña como **`712 ms`** porque le has dicho que son segundos.
> Sin unidad verías `0.712` a secas y tendrías que adivinar de qué. Configurar la
> unidad no es cosmética: es lo que permite leer el panel sin pensar.

Tres detalles que hacen fallar esta consulta si se te escapan:

1. El nombre **termina en `_bucket`**. `histogram_quantile` lee los buckets del
   histograma, no la métrica base. Sin ese sufijo devuelve `NaN`.
2. El `sum by (le)` es obligatorio. `le` es la etiqueta que marca el límite de
   cada bucket; si agregas sin conservarla, destruyes el histograma.
3. P95 significa "el 95 % de las órdenes se procesa más rápido que este valor". No
   es el promedio, y por eso es útil: el promedio esconde a los usuarios que
   esperan.

### Panel 4 — Profundidad de la cola

- **Consulta:**

  ```promql
  orderflow_queue_depth
  ```

- **Tipo:** Gauge
- **Título:** `Profundidad de la cola`
- **Standard options:** Min `0`, Max `100`
- **Thresholds:** amarillo en `30`, rojo en `70`

Aquí **no** se usa `rate()`. Es un gauge: sube y baja solo, ya es el valor actual.
Aplicarle `rate()` daría un sinsentido.

Este panel responde a una pregunta concreta: ¿el processor va al ritmo del
generator? Si la cola crece sin parar, no.

> **Va a marcar 0, y ésa es la buena noticia.** El generator crea un pedido por
> segundo y el processor tarda milisegundos en atenderlo: nunca se acumula nada.
> Los umbrales de 30 y 70 no se alcanzan en un sistema sano.
>
> El problema es que un gauge en cero se parece mucho a un gauge sin datos. Así que
> **haz que se mueva**: para el processor y mira la aguja.
>
> ```powershell
> docker compose stop order-processor
> ```
>
> El generator sigue creando pedidos y ya no los recoge nadie. En menos de un minuto
> la aguja entra en amarillo, y luego en rojo. Es la primera vez en el curso que ves
> el sistema enfermando en directo.
>
> ```powershell
> docker compose start order-processor
> ```
>
> Y observa cómo se vacía **de golpe**: el processor se pone al día en segundos. Eso
> también enseña algo — la diferencia entre un atasco que se recupera solo y uno que
> no.

---

## Bloque 3 — Infraestructura y la variable `$region`

### Panel 5 — Conexiones a Postgres

- **Consulta:**

  ```promql
  pg_stat_database_numbackends{datname="orderflow_dw"}
  ```

- **Tipo:** Stat
- **Título:** `Infraestructura — Conexiones activas a Postgres`

Esta métrica **no lleva el prefijo `orderflow_`** y eso no es un error. Viene de
`postgres-exporter`, que añadiste en la Sesión 2, no de nuestro código Python. El
prefijo `orderflow_` marca lo que instrumentamos nosotros; `pg_` marca lo que
traduce el exporter.

> **Comprueba el nombre tú mismo antes de escribirlo.** Los nombres que expone un
> exporter dependen de su versión y de qué colectores tenga activos. Nunca los des
> por sabidos:
>
> La forma más simple: abre `http://localhost:9187/metrics` en el navegador y
> busca `numbackends` con `Ctrl+F`.
>
> Desde **PowerShell**:
>
> ```powershell
> (Invoke-WebRequest -UseBasicParsing http://localhost:9187/metrics).Content -split "`n" | Select-String "pg_stat_database_numbackends"
> ```
>
> Si no devuelve nada, busca cuál sí existe con
> `numbackends` en `http://localhost:9187/metrics`, busca `pg_stat_database` y usa
> ese nombre. Este gesto —preguntarle al `/metrics` en vez de confiar en la
> memoria— es el que te va a ahorrar más tiempo en tu trabajo.

### La variable `$region`

Ahora mismo el panel de throughput dibuja todas las regiones mezcladas. Vamos a
darle un filtro.

**Paso 10.** **Dashboard settings** (el engranaje) **→ Variables → New variable**.

| Campo | Valor |
|---|---|
| Select variable type | `Query` |
| Name | `region` |
| Label | `Región` |
| Data source | `Prometheus` |
| **Query type** | **`Classic query`** |
| Query | `label_values(orderflow_orders_processed_total, region)` |
| Multi-value | **activado** |
| Include All option | **activado** |

Esa línea se lee tal cual: «dame los valores distintos de la etiqueta `region` en
esa métrica». **No escribes las regiones a mano: las descubre solas.** Si mañana la
empresa abre en Tacna, el desplegable la incluye sin que nadie toque nada.

> **Por qué `Classic query` y no `Label values`.** El desplegable ofrece también
> `Label values`, que abre un formulario con campos separados. Funciona, pero **esa
> pantalla cambia entre versiones de Grafana** y es fácil que la tuya no coincida
> con lo que diga cualquier manual. La consulta clásica es una sola línea, no
> depende de la disposición de la pantalla, y es la sintaxis que vas a encontrar en
> la documentación y en cualquier foro.

Abajo, en **Preview of values**, deben aparecer tus regiones. **Son cinco**:
arequipa, cusco, lima, piura y trujillo. Cuéntalas — es fácil que una se te
escape entre las demás, y esa confusión ya apareció en la Sesión 1.

Si el preview sale vacío, revisa el nombre de la métrica.

**No actives Multi-value e Include All a medias:** sin ellas, el desplegable te deja
elegir una región y ninguna forma de volver a verlas todas.

**Paso 11.** **Apply → Save dashboard.** Ponle de título `OrderFlow — Overview`.

**Paso 12.** Edita el **Panel 1** y cambia su consulta para que use la variable:

```promql
rate(orderflow_orders_processed_total{region=~"$region"}[1m])
```

Usa `=~` (coincide con expresión regular), no `=`. Con la opción *Multi-value*
activada, Grafana sustituye `$region` por `lima|arequipa|cusco`, y eso solo casa
con el operador de expresión regular.

**Paso 13.** Guarda y prueba el desplegable **Región** de arriba a la izquierda.
Un solo dashboard sirve ahora para todas las regiones. Sin variables, harían falta
tantos dashboards duplicados como regiones.

---

## Bloque 4 — Del clic al archivo: el dashboard como código

Todo lo que has construido vive en la base de datos interna de Grafana, dentro del
volumen `grafana_data`. Vamos a demostrar por qué eso no basta, y a arreglarlo.

**Paso 14.** **Dashboard settings → JSON Model.** Ahí está tu dashboard entero:
paneles, consultas, umbrales, la variable. Es un documento de texto.

Pulsa **Copy to clipboard**.

**Paso 15.** Guárdalo en tu repositorio, en la carpeta que creaste en el Paso 1 y
que Docker está montando dentro de Grafana:

```
grafana/dashboards/orderflow-overview.json
```

Pega el contenido tal cual y guarda el archivo.

**Paso 16.** Busca en ese JSON la línea `"id": <número>` de las primeras líneas y
cámbiala por:

```json
"id": null,
```

El `id` es el identificador interno de *tu* base de datos de Grafana. Si lo dejas,
Grafana intentará provisionar el dashboard sobre un id que en otra máquina
pertenece a otro dashboard. Con `null`, cada instalación le asigna el suyo.

Comprueba también que exista una línea `"uid": "orderflow-overview"`. Tu JSON
traerá un código aleatorio como `afxop4h0b5ds0f`: cámbialo por ese. Es el mismo
problema del `uid` de los datasources del Paso 2, ahora en el dashboard — un
identificador que solo significa algo en tu máquina.

> **Revisa también si se ha colado suciedad de la interfaz.** Busca la palabra
> `__systemRef`. Si aparece, verás un bloque parecido a éste:
>
> ```json
> "overrides": [{ "__systemRef": "hideSeriesFrom", ... }]
> ```
>
> Eso **no lo escribiste tú**: lo genera Grafana cuando haces clic en el nombre de
> una serie en la leyenda para ocultarla. Es un gesto de un segundo que queda
> **grabado para siempre** en el archivo que vas a versionar. Bórralo entero.
>
> Es la primera vez en el curso que ves que la herramienta escribe cosas que no le
> pediste. Y es, precisamente, uno de los mejores argumentos para pasar a código:
> en un archivo puedes verlo y quitarlo; dentro de una base de datos, no.

**Paso 17.** Espera 30 segundos —el provider relee la carpeta en ese intervalo— y
recarga Grafana. Ve a **Dashboards**.

Ahora verás **dos**: en la carpeta `OrderFlow`, el provisionado desde tu archivo; y
en *General*, el borrador que guardaste a clics en el Paso 9. Ábrelos: son
idénticos, porque uno salió del otro.

> 🔑 **A partir de este momento, el archivo manda.**
>
> El de la carpeta `OrderFlow` **no se edita a clics**. Puedes tocarlo, y parecerá
> que se guarda, pero el provider relee la carpeta cada treinta segundos y **lo
> devuelve a lo que diga el archivo**. Tu cambio desaparece sin ningún aviso.
>
> Para cambiar algo de ese dashboard hay dos caminos, y los dos son los correctos:
> editar el JSON directamente, o editar el borrador de *General*, exportarlo otra
> vez y sustituir el archivo.
>
> Es exactamente lo que se busca en producción, y es la razón de todo este bloque.

**Paso 18 — La prueba de fuego.** Borra el dashboard que está en `OrderFlow`
(**Dashboard settings → Delete dashboard**).

Espera 30 segundos y recarga.

**Ha vuelto.** No se puede borrar desde la interfaz algo que está definido en un
archivo: Grafana lo vuelve a crear en cuanto relee la carpeta. Eso es exactamente
lo que quieres en producción — y es la razón por la que el dashboard ahora es
código: se versiona en git, se revisa antes de fusionar, y se recrea solo en
cualquier máquina que levante el stack.

**Paso 19.** Borra el que quedó suelto en *General*, para no tener dos.

---

## Bloque 5 — Kibana: de Discover a Dashboard

> 🌐 **Cambiamos de herramienta.** Todo lo anterior era Grafana, en
> `localhost:3000`. Este bloque entero es **Kibana**, en `localhost:5601`.
>
> | | Grafana `:3000` | Kibana `:5601` |
> |---|---|---|
> | Qué contiene | métricas, los números de Prometheus | logs, los textos de Elasticsearch |
>
> Las dos tienen menús con las palabras *Dashboard* y *Create*, así que cada paso de
> aquí en adelante lleva su dirección completa.

En la Sesión 3 dejaste el Data View `orderflow-logs-*` creado y aprendiste a
buscar en Discover. Hoy conviertes esas búsquedas en gráficos.

**Paso 20.** Abre `http://localhost:5601/app/discover`. Comprueba que el Data
View es `orderflow-logs-*` y el rango de tiempo, los últimos 15 minutos.

Aplica el filtro:

```
level: "ERROR"
```

Pulsa **Save** arriba a la derecha y llámalo `Errores OrderFlow`. Una búsqueda
guardada se puede reutilizar en un dashboard sin volver a escribirla.

**Paso 21 — Visualización 1: motivos de fallo.**

> 🌐 **Sigues en Kibana**, `http://localhost:5601`. Entra directo a
> `http://localhost:5601/app/visualize` y pulsa **Create visualization → Lens**.
>
> *(Si prefieres el menú: botón **☰** → sección **Analytics** → **Visualize
> Library**. Pero fíjate en que Grafana también tiene menús con esas palabras: la
> dirección es inequívoca, el nombre de un menú no.)*

- Data view: `orderflow-logs-*`
- Tipo de gráfico: **Bar vertical**
- **Horizontal axis:** *Top values of* `reason` (o `reason.keyword` si el
  desplegable lo muestra así), tamaño 10
- **Vertical axis:** *Count of records*

Guarda como `Fallos por motivo`.

> Si el campo `reason` no aparece en la lista, es porque el filtro `level: "ERROR"`
> no está aplicado en esta pantalla y no hay documentos de fallo en el rango de
> tiempo. Amplía el rango a las últimas 4 horas.

**Paso 22 — Visualización 2: negocio contra operación.**

> 🌐 En Kibana: `http://localhost:5601/app/visualize` → **Create visualization →
> Lens**.

- Tipo de gráfico: **Pie**
- **Slice by:** *Top values of* `event_category`
- **Size by:** *Count of records*

Guarda como `Negocio vs operación`.

Ese campo `event_category` no venía en los logs. Lo creó el filtro de Logstash que
configuraste en la Sesión 3. Los datos que estás graficando ahora son consecuencia
directa de aquel archivo.

**Paso 23 — El dashboard.**

> 🌐 En Kibana: `http://localhost:5601/app/dashboards` → **Create dashboard → Add
> from library**.

Añade las dos visualizaciones y la búsqueda guardada `Errores OrderFlow`.

Guarda el dashboard como `OrderFlow — Logs`.

**Paso 24.** Ejecuta el validador:

```bash
python scripts/validate_sesion4.py
```

> **Si falla con un error de autenticación**, es que cambiaste la contraseña de
> Grafana en el Paso 6. Pásasela así:
>
> ```powershell
> $env:GRAFANA_ADMIN_PASSWORD = "la_que_pusiste"; python scripts\validate_sesion4.py
> ```

**Qué debes ver:** ocho comprobaciones en `OK` y una en `PEND` — la del Ejercicio C,
que es trabajo que aún no has hecho. `PEND` no es un fallo: es una tarea pendiente.

---

## Ejercicios (haz estos tú solo)

### Ejercicio A — Un panel propio en Grafana

Añade a `OrderFlow — Overview` un sexto panel, a tu elección entre estos dos:

- Comparar el throughput del **generator** contra el del **processor** en un mismo
  gráfico, para ver si uno se está quedando atrás del otro.
- Un `topk(3, ...)` sobre `orderflow_orders_failed_total` que muestre los tres
  motivos de fallo más frecuentes.

*Pista: los nombres exactos de las dos métricas de throughput están en
`docs/metricas.md`. Para el segundo, recuerda que un counter necesita `rate()` o
`increase()` antes de comparar magnitudes.*

### Ejercicio B — Una tercera visualización en Kibana

Añade al dashboard `OrderFlow — Logs` una visualización más: el **volumen de logs
a lo largo del tiempo, desglosado por `level`**.

*Pista: en Lens, el eje horizontal es una *Date histogram* sobre `@timestamp`, y el
desglose por color se hace con *Break down by → Top values of* `level`.*

### Ejercicio C — El panel de tu métrica

En la Sesión 2 instrumentaste `orderflow_order_amount_soles_total`. Hasta ahora
solo la habías consultado en Prometheus.

Añade a `OrderFlow — Overview` un panel que muestre el **ticket promedio por
región** usando esa métrica, guarda el dashboard, y vuelve a exportar el JSON Model
a `grafana/dashboards/orderflow-overview.json`.

Después borra el dashboard desde la interfaz y comprueba que vuelve **con tu panel
incluido**.

*Pista: el ticket promedio es el importe acumulado dividido entre las órdenes
procesadas, ambos como tasa sobre la misma ventana. La consulta la dedujiste en el
Bloque 4 de la Sesión 2.*

---

## Si algo falla

| Síntoma | Causa probable | Solución |
|---|---|---|
| Los paneles dicen `Datasource not found` | Falta el `uid` en `datasources.yml`, o Grafana no se recreó | Revisa el Paso 2; luego `docker compose up -d --force-recreate grafana` |
| Grafana no dijo `Recreated` al levantar | No se guardó el volumen del Paso 4 | Revisa `docker-compose.yml` y repite `docker compose up -d` |
| No aparece la carpeta `OrderFlow` en Dashboards | Error de sintaxis en `dashboards.yml` o en el JSON | `docker compose logs grafana --tail 30`, busca `level=error` |
| La carpeta aparece pero vacía | El archivo no está en `grafana/dashboards/` o no termina en `.json` | Comprueba la ruta y el nombre |
| **Grafana no arranca**, con `read-only file system` | La ruta del volumen cuelga dentro de `/etc/grafana/provisioning` | Debe ser `/etc/grafana/dashboards`. Pasos 3 y 4 |
| **No entra con `admin`/`admin`** | La contraseña se cambió en el primer inicio de sesión | `docker compose exec grafana grafana cli admin reset-admin-password admin` |
| **El dashboard del archivo no aparece**, y los logs no dan error | Choca con otro del mismo título en la misma carpeta | El borrador va en `General` con otro nombre. Paso 9 |
| Un cambio en `dashboards.yml` no surte efecto | Grafana lee la configuración del provider **solo al arrancar** | `docker compose restart grafana` |
| Errores `EOF` al leer el JSON | Se leyó el archivo mientras estaba a medio guardar | Mira **la hora** del error: si es anterior a tu último guardado, ya está resuelto |
| No hay dónde escribir la consulta | La zona de consulta está en modo **Builder** | Pulsa **Code** |
| El validador dice que no existe una métrica que sí escribiste | Estás en una versión anterior del validador | Actualiza el repositorio: se corrigió tras el simulacro |
| El panel P95 muestra `NaN` | Falta `_bucket` o falta `sum by (le)` | Revisa el Paso 9, Panel 3 |
| El panel de Postgres sale vacío | Ese nombre de métrica no existe en tu exporter | Búscalo en `http://localhost:9187/metrics`, Panel 5 |
| El desplegable `Región` sale vacío | La métrica de la variable está mal escrita | Revisa el Paso 10, campo *Metric* |
| En Kibana no aparece el campo `reason` | No hay documentos de fallo en el rango | Amplía el rango de tiempo a 4 horas |
| El dashboard borrado no vuelve | Aún no pasaron 30 s, o el archivo no se guardó | Espera y recarga; comprueba el archivo en disco |

Para cualquier otro problema: `docs/troubleshooting.md`.

---

## Antes de la Sesión 5

1. **Baja el stack:** `docker compose down` (sin `-v`).

   Ahora puedes hacerlo sin miedo: tu dashboard está en un archivo, no en el
   volumen.

2. **Deja tu `orderflow-overview.json` guardado.** La Sesión 5 lo da por hecho.

3. **Descarga de la plataforma** los cuatro archivos de la Sesión 5: `app.py`,
   `Dockerfile`, `requirements.txt` y `orderflow-alerts.yml`.

4. **Lee** `docs/alertas_intro.md`. Es corto y da el contexto de la próxima sesión.

5. **Completa el entregable** con la plantilla `scripts/entregable_template.md`.

> En la Sesión 5 se llena la tercera y última caja: Alertmanager. La consulta del
> panel de tasa de error deja de ser un color en pantalla y pasa a ser un correo
> que llega solo, aunque no haya nadie mirando.
