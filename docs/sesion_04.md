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

Abre `grafana/provisioning/datasources/datasources.yml`. Verás dos datasources
declarados, `Prometheus` y `Elasticsearch`.

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

Abre `grafana/provisioning/dashboards/dashboards.yml`. Hoy dice:

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
      # Esta ruta es la de DENTRO del contenedor. docker-compose.yml
      # monta ./grafana/dashboards del repo justo aqui.
      path: /etc/grafana/provisioning/dashboards/json
      foldersFromFilesStructure: false
```

### Paso 4 — Montar la carpeta dentro de Grafana

Grafana todavía no puede ver tu carpeta `grafana/dashboards/`: está fuera del
contenedor. Hay que montarla.

Abre `docker-compose.yml`, busca el servicio `grafana` y su sección `volumes:`:

```yaml
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
```

Añade una tercera línea debajo:

```yaml
      # Sesion 4: los dashboards viven versionados en el repo. El provider
      # "orderflow" de grafana/provisioning/dashboards/dashboards.yml lee
      # de esta ruta de dentro del contenedor.
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards/json:ro
```

### Paso 5 — Levantar y comprobar

```bash
docker compose up -d
```

Fíjate en la salida. Doce servicios dirán `Running`; **Grafana dirá `Recreated`**.
Es el único que cambió: tiene un volumen nuevo. Los demás ni se enteran.

```bash
docker compose logs grafana --tail 20
```

No debe haber líneas con `level=error`.

> **Si Grafana no dice `Recreated`**, es que el cambio del `docker-compose.yml` no
> se guardó. Sin ese volumen, el resto de la sesión no funciona.

---

## Bloque 1 — Grafana ya tiene los datos conectados

**Paso 6.** Abre `http://localhost:3000`. Usuario `admin`, contraseña `admin`.
Si te pide cambiarla, puedes saltar el paso.

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

**Paso 8.** Ve a **Explore** (el icono de la brújula), elige el datasource
**Prometheus** y ejecuta:

```promql
orderflow_orders_processed_total
```

Es la misma consulta de la Sesión 1, pero aquí no hay que salir a otra herramienta.
Explore es para investigar; los dashboards son para vigilar.

---

## Bloque 2 — Los cuatro paneles de negocio

**Paso 9.** **Dashboards → New → New dashboard → Add visualization**. Elige el
datasource **Prometheus**.

Cada panel se construye igual: escribes la consulta abajo, eliges el tipo de
visualización arriba a la derecha, ajustas las opciones del panel y pulsas
**Save dashboard** (o **Back to dashboard** para seguir añadiendo).

### Panel 1 — Throughput

- **Consulta:**

  ```promql
  rate(orderflow_orders_processed_total[1m])
  ```

- **Tipo:** Time series
- **Título:** `Throughput (órdenes/seg)`
- **Legend → Legend format:** `{{region}}`
- **Standard options → Unit:** `requests/sec (rps)`

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

### Panel 3 — Latencia P95

- **Consulta:**

  ```promql
  histogram_quantile(0.95, sum by (le) (rate(orderflow_processing_duration_seconds_bucket[5m])))
  ```

- **Tipo:** Time series
- **Título:** `Latencia P95 (seg)`
- **Standard options → Unit:** `seconds (s)`

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
> ```bash
> curl -s http://localhost:9187/metrics | grep "^# HELP pg_stat_database_numbackends"
> ```
>
> En PowerShell:
>
> ```powershell
> (Invoke-WebRequest http://localhost:9187/metrics).Content -split "`n" |
>   Select-String "^# HELP pg_stat_database_numbackends"
> ```
>
> Si no devuelve nada, busca cuál sí existe con
> `curl -s http://localhost:9187/metrics | grep "^# HELP pg_stat_database"` y usa
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
| Query type | `Label values` |
| Label | `region` |
| Metric | `orderflow_orders_processed_total` |
| Multi-value | activado |
| Include All option | activado |

Abajo, en **Preview of values**, deben aparecer tus regiones. Si sale vacío, la
métrica está mal escrita.

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

Comprueba también que exista una línea `"uid": "orderflow-overview"`. Si tu JSON
trae otro uid, cámbialo por ese: es el que va a buscar el validador.

**Paso 17.** Espera 30 segundos —el provider relee la carpeta en ese intervalo— y
recarga Grafana. Ve a **Dashboards**. Ahora verás **una carpeta llamada
`OrderFlow`** que antes no existía, y dentro, tu dashboard.

Ese de la carpeta es el provisionado desde archivo. El que guardaste a clics sigue
suelto en *General*.

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

En la Sesión 3 dejaste el Data View `orderflow-logs-*` creado y aprendiste a
buscar en Discover. Hoy conviertes esas búsquedas en gráficos.

**Paso 20.** Abre `http://localhost:5601` → **Discover**. Comprueba que el Data
View es `orderflow-logs-*` y el rango de tiempo, los últimos 15 minutos.

Aplica el filtro:

```
level: "ERROR"
```

Pulsa **Save** arriba a la derecha y llámalo `Errores OrderFlow`. Una búsqueda
guardada se puede reutilizar en un dashboard sin volver a escribirla.

**Paso 21 — Visualización 1: motivos de fallo.**

**Analytics → Visualize Library → Create visualization → Lens.**

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

Nueva visualización Lens:

- Tipo de gráfico: **Pie**
- **Slice by:** *Top values of* `event_category`
- **Size by:** *Count of records*

Guarda como `Negocio vs operación`.

Ese campo `event_category` no venía en los logs. Lo creó el filtro de Logstash que
configuraste en la Sesión 3. Los datos que estás graficando ahora son consecuencia
directa de aquel archivo.

**Paso 23 — El dashboard.**

**Analytics → Dashboard → Create dashboard → Add from library.** Añade las dos
visualizaciones y la búsqueda guardada `Errores OrderFlow`.

Guarda el dashboard como `OrderFlow — Logs`.

**Paso 24.** Ejecuta el validador:

```bash
python scripts/validate_sesion4.py
```

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
