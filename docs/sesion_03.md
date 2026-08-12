# Manual de práctica — Sesión 3

## Logs con Logstash y Elasticsearch

**Capítulo 1:** Observabilidad y captura de datos operativos

---

## Qué vas a construir hoy

Hoy **Kibana deja de estar vacío**. Es la primera de las tres cajas que se llenan.

El stack sigue teniendo 13 servicios: hoy no añadimos ninguno. Lo que cambia es
que dos flujos de logs que hasta ahora solo pasaban por tu pantalla van a
convertirse en datos consultables.

Y hay una dificultad real: tus dos servicios loguean **de forma distinta**.

| Servicio | Formato | Cómo llega a Logstash |
|---|---|---|
| `order-processor` | JSON estructurado | TCP 5044, directo desde Python |
| `order-generator` | Texto plano | syslog UDP 5000, vía driver de Docker |

Al terminar, los dos estarán en el mismo índice de Elasticsearch, con los mismos
campos, y podrás cruzarlos en una sola consulta.

---

## Punto de partida

### Paso 0 — Sincronizar tu código

**Este paso solo te afecta si hiciste el ejercicio de instrumentación de la
Sesión 2.** Si lo hiciste, tu `processor.py` difiere del repositorio, y `git pull`
te dará un conflicto.

Primero comprueba si es tu caso:

```bash
git status
```

Si aparece `modified: services/order-processor/processor.py`, haz esto:

```bash
git checkout -- services/order-processor/processor.py
```

Ese comando descarta tu versión local y toma la del repositorio. **No pierdes
nada:** a partir de esta sesión, la métrica `orderflow_order_amount_soles_total`
viene ya incluida en el repo, con la misma implementación que escribiste tú (y
comentada, por si quieres comparar).

> Si quieres conservar tu versión para compararla, cópiala antes:
> `cp services/order-processor/processor.py mi_processor_sesion2.py`

### Paso 1 — Actualizar y levantar

```bash
git pull
docker compose up -d
```

**Qué debes ver:** Docker **recrea** `order-generator` y `logstash`, y deja
`Running` los otros 11. El generator se recrea porque cambió su configuración de
logging; Logstash porque abrió un puerto nuevo.

> No hace falta que toques tu `.env`. La variable nueva `LOGSTASH_SYSLOG_PORT`
> tiene el valor 5000 por defecto en `docker-compose.yml`.

Confirma que sigues teniendo todo:

```bash
docker compose ps
```

**Qué debes ver:** 13 filas.

---

## Bloque 1 — Ver el problema antes de resolverlo

### Paso 2 — Dos formas de decir lo mismo

```bash
docker compose logs order-processor --tail 3
```

```json
{"timestamp":"2026-08-12 03:12:15,842","level":"INFO","service":"processor","message":"Order processed","event":"order_processed","order_id":"8c4a2f9b","region":"lima","total_amount":127.5}
```

Ahora el otro:

```bash
docker compose logs order-generator --tail 3
```

```
2026-08-12 03:12:15,481 INFO - Order generated: id=8c4a2f9b, region=lima, items=3, total=S/127.50
```

**Los dos contienen la misma información.** Región, importe, identificador. Pero
el primero ya viene en campos y el segundo es una cadena de texto donde esos
campos están *escondidos*.

Con el primero puedes preguntar "dame las órdenes de Lima de más de 500 soles".
Con el segundo no puedes preguntar nada: solo buscar texto.

### Paso 3 — Por qué el generator no se arregla en el código

La tentación es cambiar el generator para que también emita JSON. **En este curso
no lo hacemos a propósito**, porque en tu trabajo real te vas a encontrar
exactamente esto: sistemas heredados, software de terceros y servicios que no
puedes modificar.

La solución profesional no es cambiar el origen: es **estructurar en el camino**.
De eso se encarga Logstash.

---

## Bloque 2 — Los dos caminos hacia Logstash

### Paso 4 — El camino del processor: TCP

Está funcionando desde la Sesión 1. En `services/order-processor/processor.py`,
la clase `LogstashTCPHandler` abre un socket TCP contra `logstash:5044` y manda
cada log como JSON terminado en salto de línea.

Del otro lado, en `logstash/pipeline/orderflow.conf`:

```ruby
tcp {
  port => 5044
  codec => json_lines
  tags => ["orderflow", "processor"]
}
```

`json_lines` es el códec que entiende ese formato. Y `tags` marca el origen: nos
va a servir para procesar cada flujo por separado.

### Paso 5 — El camino del generator: el driver de Docker

Al generator no le tocamos ni una línea de código. Lo que cambió está en
`docker-compose.yml`:

```yaml
logging:
  driver: syslog
  options:
    syslog-address: "udp://localhost:5000"
    tag: "order-generator"
```

Con eso, **Docker intercepta todo lo que el contenedor escribe** en su salida
estándar y lo reenvía por syslog.

> **La línea que confunde a todo el mundo: ¿por qué `localhost` y no `logstash`?**
>
> Porque el driver de logging **no corre dentro del contenedor**: corre en el
> demonio de Docker, fuera de la red de Compose. Ahí `logstash` no significa nada,
> porque el DNS interno de Compose no existe. Pero el puerto 5000 está publicado
> en la máquina, y el demonio sí lo alcanza por `localhost`.
>
> Es de los errores más difíciles de diagnosticar cuando se hace mal, porque no
> da ningún mensaje: los logs simplemente no llegan.

Y en Logstash:

```ruby
syslog {
  port => 5000
  tags => ["orderflow", "generator"]
}
```

### Paso 6 — Verificar que los dos flujos llegan

```bash
docker compose logs logstash --tail 30
```

**Qué debes ver:** líneas indicando que el pipeline arrancó y que los inputs
están escuchando. No debe haber errores en rojo.

Y la prueba definitiva, contra Elasticsearch:

```bash
curl -s "http://localhost:9200/orderflow-logs-*/_count"
```

En PowerShell: `Invoke-RestMethod "http://localhost:9200/orderflow-logs-*/_count"`

**Qué debes ver:** un JSON con `"count"` mayor que cero, que **crece** si repites
el comando pasados unos segundos.

---

## Bloque 3 — Estructurar el texto plano con grok

### Paso 7 — Qué hace grok

`grok` toma una cadena de texto y extrae campos con un patrón. Abre
`logstash/pipeline/orderflow.conf` y busca el bloque `generator`:

```ruby
grok {
  match => {
    "message" => "Order generated: id=%{DATA:order_id_short}, region=%{WORD:region}, items=%{NUMBER:items_count:int}, total=S/%{NUMBER:total_amount:float}"
  }
}
```

Cada `%{TIPO:nombre}` captura un trozo y lo guarda como campo:

| Fragmento | Extrae | Tipo resultante |
|---|---|---|
| `%{DATA:order_id_short}` | El identificador | texto |
| `%{WORD:region}` | La región | texto |
| `%{NUMBER:items_count:int}` | Nº de artículos | **entero** |
| `%{NUMBER:total_amount:float}` | El importe | **decimal** |

> **El `:int` y el `:float` importan mucho.** Sin ellos, Elasticsearch guardaría
> `"127.50"` como texto, y no podrías hacer sumas, promedios ni filtrar por
> "mayor que". Con ellos, `total_amount` es un número de verdad.

### Paso 8 — Los dos detalles que evitan errores silenciosos

Fíjate en dos cosas del archivo, porque son las que diferencian una configuración
que funciona de una que parece funcionar.

**1. El grok está dentro de un condicional:**

```ruby
if [message] =~ /Order generated:/ {
```

El generator también emite logs de arranque y de reconexión que no siguen ese
formato. Sin el condicional, cada uno de ellos añadiría una etiqueta
`_grokparsefailure` y ensuciaría el índice con falsos errores.

**2. El filtro `date` declara el formato explícito:**

```ruby
date {
  match => [ "timestamp", "yyyy-MM-dd HH:mm:ss,SSS", "ISO8601" ]
  ...
}
```

El processor emite `2026-08-12 03:12:15,842`: separador **espacio** en vez de `T`,
y **coma** decimal en vez de punto. Eso no es ISO8601 estricto. Si se dejara solo
`ISO8601`, el parseo fallaría **en silencio**: el evento entraría igual, pero con
`@timestamp` puesto a la hora de ingesta en lugar de la hora real, y con una
etiqueta `_dateparsefailure`.

El síntoma en producción es horrible: los logs aparecen desplazados unos segundos
respecto a las métricas, y correlacionar un incidente se vuelve imposible.

### Paso 9 — Comprobar que no hay fallos de parseo

```bash
curl -s "http://localhost:9200/orderflow-logs-*/_count?q=tags:_grokparsefailure"
curl -s "http://localhost:9200/orderflow-logs-*/_count?q=tags:_dateparsefailure"
```

**Qué debes ver:** `"count":0` en los dos.

Si alguno da un número mayor que cero, algo no está parseando. Es exactamente el
tipo de comprobación que hay que hacer en un pipeline real y que casi nadie hace.

---

## Bloque 4 — Consultar en Kibana

### Paso 10 — Crear el Data View

Abre `http://localhost:5601` → menú lateral → **Discover**.

Si ya lo creaste en la Sesión 1, sáltate esto. Si no:

1. **Create data view**
2. **Name:** `orderflow-logs`
3. **Index pattern:** `orderflow-logs-*`
4. **Timestamp field:** `@timestamp`
5. **Save data view to Kibana**

**Qué debes ver:** el histograma de eventos y la lista de documentos. Si sale
vacío, pon el rango de tiempo en **Last 15 minutes** y pulsa **Refresh**.

### Paso 11 — Comprobar que los dos orígenes conviven

En la barra de búsqueda (esto es **KQL**, el lenguaje de consulta de Kibana):

```
tags: "generator"
```

y después:

```
tags: "processor"
```

**Qué debes ver:** documentos en los dos casos. Los del generator ahora tienen
campos `region`, `items_count` y `total_amount`, que **no existían en el texto
original**: los creó grok.

### Paso 12 — Consultas KQL que vas a usar de verdad

```
event: "order_failed"
```
Solo las órdenes que fallaron.

```
event: "order_failed" and reason: "postgres_timeout"
```
Solo las que fallaron por ese motivo concreto.

> Los valores posibles de `reason` están en `docs/metricas.md`. **`db_error` no
> existe**: si filtras por él no obtendrás nada, y no es porque no haya errores.

```
event_category: "business" and total_amount > 500
```
Órdenes grandes, de cualquiera de los dos orígenes.

```
region: "lima" and not level: "INFO"
```
Todo lo que no sea informativo, en una región concreta.

### Paso 13 — La correlación, que es el objetivo real

Éste es el ejercicio que resume las tres primeras sesiones.

1. En **Prometheus** (`localhost:9090`), ejecuta:

   ```promql
   increase(orderflow_orders_failed_total[15m])
   ```

   Anota **qué causa** tiene el valor más alto.

2. En **Kibana**, con el rango de tiempo en los últimos 15 minutos, busca esa
   misma causa:

   ```
   event: "order_failed" and reason: "TU_CAUSA_AQUI"
   ```

3. Abre uno de los documentos (flecha a la izquierda de la fila) y localiza el
   `order_id` concreto.

Acabas de recorrer el camino completo: **la métrica te dijo que había un problema
y cuál era el más frecuente; el log te dijo exactamente qué orden lo sufrió y
cuándo.** Ninguna de las dos herramientas podía darte eso sola.

---

## Ejercicios (haz estos tú solo)

### Ejercicio A — La región problemática

Usando Kibana, averigua **qué región tiene más órdenes fallidas** en la última
hora.

*Pista: filtra por `event: "order_failed"`, luego busca el campo `region` en el
panel izquierdo y pulsa **Visualize**.*

### Ejercicio B — Generadas contra procesadas

Escribe dos consultas KQL, una que cuente los eventos `order_generated` y otra
los `order_processed`, en la misma ventana de tiempo. Anota los dos números.

¿Coinciden? Explica en dos líneas a qué se debe la diferencia.

### Ejercicio C — Un campo nuevo con grok

El generator emite un campo que **no** estamos extrayendo: el nivel de log
(`INFO`, `WARNING`, `ERROR`) del texto original.

Propón (solo escríbelo, no hace falta que lo apliques) el patrón grok que
extraería la marca de tiempo y el nivel del principio de la línea:

```
2026-08-12 03:12:15,481 INFO - Order generated: ...
```

*Pista: existe un patrón predefinido llamado `TIMESTAMP_ISO8601` y otro llamado
`LOGLEVEL`.*

---

## Si algo falla

| Síntoma | Causa probable | Solución |
|---|---|---|
| `git pull` da conflicto en `processor.py` | Hiciste el ejercicio de S2 | Paso 0 de este manual |
| No entran logs del generator | El driver de logging no se aplicó | `docker compose up -d --force-recreate order-generator` |
| Logstash no arranca | Error de sintaxis en el `.conf` | `docker compose logs logstash --tail 40` |
| `_count` de Elasticsearch da 0 | Logstash aún no arrancó | Espera 60 s; Logstash tarda |
| Aparece `_grokparsefailure` | El patrón no casa con el texto | Compara el patrón con una línea real |
| Aparece `_dateparsefailure` | Formato de fecha no contemplado | Revisa el bloque `date` del Paso 8 |
| Discover vacío pero `_count` > 0 | Rango de tiempo o Data View | "Last 15 minutes" + Refresh |
| Los logs salen desfasados unos segundos | El filtro `date` no está parseando | Comprueba `_dateparsefailure` |

---

## Antes de la Sesión 4

1. **Baja el stack:** `docker compose down` (sin `-v`).
2. **Lee** `docs/grafana_kibana_intro.md`.
3. **Completa el entregable** con la plantilla `scripts/entregable_template.md`.

> Con esto termina el Capítulo 1: ya sabes **capturar** métricas y logs. El
> Capítulo 2 empieza por hacerlos visibles. En la Sesión 4 se llena la segunda
> caja: Grafana.
