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

Necesitas dos cosas:

1. El stack de la Sesión 2 funcionando: **13 servicios**.
2. El archivo **`orderflow.conf`** descargado de la plataforma del curso.

```bash
docker compose up -d
docker compose ps
```

**Qué debes ver:** 13 filas, todas `Up` o `healthy`.

> **Tu métrica de la Sesión 2 sigue ahí.** El `Counter` que escribiste en
> `processor.py` es tuyo y nadie lo va a tocar. Compruébalo si quieres:
> abre `http://localhost:8001/metrics` en el navegador y busca `order_amount`
> con `Ctrl+F`.

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

Varios pasos de hoy te piden pegar bloques largos. **Al copiarlos desde el
documento de Word, los espacios del principio de cada línea se pierden.** Y esos
espacios no son decoración: son lo único que indica qué pertenece a qué.

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

## Bloque 1 — Ver el problema antes de resolverlo

### Paso 1 — Dos formas de decir lo mismo

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

### Paso 2 — Por qué el generator no se arregla en el código

La tentación es cambiar el generator para que también emita JSON. **En este curso
no lo hacemos a propósito**, porque en tu trabajo real te vas a encontrar
exactamente esto: sistemas heredados, software de terceros y servicios que no
puedes modificar.

La solución profesional no es cambiar el origen: es **estructurar en el camino**.
De eso se encarga Logstash.

---

## Bloque 2 — Abrir el segundo camino hacia Logstash

El camino del `order-processor` ya funciona desde la Sesión 1: manda su JSON por
TCP al puerto 5044. El del `order-generator` no existe todavía. Lo vas a abrir tú.

### Paso 3 — Añadir el puerto syslog a Logstash

Abre `docker-compose.yml` y busca el servicio `logstash`. Dentro de su sección
`ports:` verás una sola línea:

```yaml
    ports:
      - "${LOGSTASH_TCP_PORT:-5044}:5044"
```

Añade debajo estas tres líneas:

```yaml
      # SESION 3: input syslog para los logs de texto plano del generator.
      # Es UDP, no TCP: el driver syslog de Docker envia por datagramas.
      - "${LOGSTASH_SYSLOG_PORT:-5000}:5000/udp"
```

> **Fíjate en el `/udp` del final.** Sin él, Docker abriría el puerto en TCP y los
> datagramas de syslog se perderían sin dar ningún error.

### Paso 4 — Enrutar los logs del generator

Al generator no le vas a tocar ni una línea de código. Todo se resuelve en
`docker-compose.yml`.

Busca el servicio `order-generator` y localiza el final de su bloque:

```yaml
    depends_on:
      redis:
        condition: service_healthy
```

Pega esto justo debajo:

```yaml
    # --- SESION 3: enrutar los logs de texto plano hacia Logstash ---
    # El driver de logging de Docker corre a nivel del daemon (dockerd),
    # NO dentro de la red del contenedor. Por eso NO resuelve nombres de
    # servicio de Compose como "logstash". Como dockerd y el puerto
    # publicado de Logstash conviven en la misma maquina (o en la VM de
    # Docker Desktop), "localhost" si funciona.
    logging:
      driver: syslog
      options:
        syslog-address: "udp://localhost:${LOGSTASH_SYSLOG_PORT:-5000}"
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

### Paso 5 — Declarar el puerto en tu `.env`

Abre el archivo `.env` (no el `.env.example`) y busca la sección `# --- Logstash ---`.
Añade la variable nueva debajo de `LOGSTASH_TCP_PORT`:

```
# Puerto syslog (UDP): recibe el texto plano del order-generator,
# enrutado por el driver de logging de Docker. Anadido en la Sesion 3.
LOGSTASH_SYSLOG_PORT=5000
```

> Aunque el `docker-compose.yml` ya trae `:-5000` como valor por defecto, es buena
> costumbre declararla: quien lea el `.env` verá todos los puertos del stack en un
> solo sitio.

### Paso 6 — Instalar el pipeline de Logstash

Este archivo sí te lo damos hecho, porque son 120 líneas de configuración y hoy
lo importante es **entenderlo**, no teclearlo.

Coge el archivo **`orderflow.conf`** que descargaste de la plataforma y cópialo
a la carpeta del pipeline, **reemplazando el que ya está**:

**Windows (PowerShell):**
```powershell
Copy-Item "$HOME\Downloads\orderflow.conf" .\logstash\pipeline\orderflow.conf -Force
```

**Mac/Linux:**
```bash
cp ~/Downloads/orderflow.conf logstash/pipeline/orderflow.conf
```

Ajusta la ruta de origen si lo descargaste a otra carpeta.

Comprueba que se copió bien:

```bash
docker compose config --services
```

**Qué debes ver:** los 13 nombres de siempre, sin errores de sintaxis.

### Paso 7 — Aplicar los cambios

```bash
docker compose up -d --force-recreate order-generator logstash
```

**Qué debes ver:** Docker **recrea** esos dos servicios y deja `Running` los
otros 11.

> **¿Por qué `--force-recreate`?** Porque el driver de logging se asigna cuando el
> contenedor **se crea**, no cuando se reinicia. Un `docker compose restart` no
> serviría: el generator seguiría escribiendo a la salida estándar de siempre y
> los logs no llegarían nunca. Es un fallo silencioso clásico.

Confirma que sigues teniendo todo:

```bash
docker compose ps
```

**Qué debes ver:** 13 filas.

### Paso 8 — Verificar que los dos flujos llegan

```bash
docker compose logs logstash --tail 30
```

**Qué debes ver:** líneas indicando que el pipeline arrancó y que los inputs
están escuchando. No debe haber errores en rojo.

Y la prueba definitiva, contra Elasticsearch:

En **PowerShell**:

```powershell
Invoke-RestMethod "http://localhost:9200/orderflow-logs-*/_count"
```

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
curl -s "http://localhost:9200/orderflow-logs-*/_count"
```

</details>

**Qué debes ver:** un JSON con `"count"` mayor que cero, que **crece** si repites
el comando pasados unos segundos.

---

## Bloque 3 — Entender lo que acabas de instalar

Abre `logstash/pipeline/orderflow.conf` en VS Code. Tiene tres secciones:
`input`, `filter` y `output`.

### Paso 9 — Los dos inputs

```ruby
tcp {
  port => 5044
  codec => json_lines
  tags => ["orderflow", "processor"]
}

syslog {
  port => 5000
  tags => ["orderflow", "generator"]
}
```

`json_lines` es el códec que entiende el formato del processor: un JSON completo
por línea. Y `tags` marca el origen de cada evento — eso es lo que permite
procesar cada flujo por separado más abajo.

### Paso 10 — Qué hace grok

`grok` toma una cadena de texto y extrae campos con un patrón. Busca el bloque
del `generator`:

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

### Paso 11 — Los dos detalles que evitan errores silenciosos

Éstos son los que diferencian una configuración que funciona de una que **parece**
funcionar.

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

### Paso 12 — Comprobar que no hay fallos de parseo

En **PowerShell**:

```powershell
Invoke-RestMethod "http://localhost:9200/orderflow-logs-*/_count?q=tags:_grokparsefailure"
Invoke-RestMethod "http://localhost:9200/orderflow-logs-*/_count?q=tags:_dateparsefailure"
```

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
curl -s "http://localhost:9200/orderflow-logs-*/_count?q=tags:_grokparsefailure"
curl -s "http://localhost:9200/orderflow-logs-*/_count?q=tags:_dateparsefailure"
```

</details>

**Qué debes ver:** `"count":0` en los dos.

Si alguno da un número mayor que cero, algo no está parseando. Es exactamente el
tipo de comprobación que hay que hacer en un pipeline real y que casi nadie hace.

---

## Bloque 4 — Consultar en Kibana

### Paso 13 — Crear el Data View

Abre `http://localhost:5601/app/discover`.

> Entra por esa dirección completa, no por `localhost:5601` a secas: esa última
> te lleva a la pantalla de bienvenida de Kibana, que oculta el menú lateral.
> Es lo mismo que viste en la Sesión 1.

Si ya creaste el Data View en la Sesión 1, sáltate esto. Si no:

1. **Create data view**
2. **Name:** `orderflow-logs`
3. **Index pattern:** `orderflow-logs-*`
4. **Timestamp field:** `@timestamp`
5. **Save data view to Kibana**

**Qué debes ver:** el histograma de eventos y la lista de documentos. Si sale
vacío, pon el rango de tiempo en **Last 15 minutes** y pulsa **Refresh**.

### Paso 14 — Comprobar que los dos orígenes conviven

En la misma barra de búsqueda de la Sesión 1 —la caja ancha de arriba, entre el
Data View y el selector de fechas— escribe esta consulta **KQL**:

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

### Paso 15 — Consultas KQL que vas a usar de verdad

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

### Paso 16 — La correlación, que es el objetivo real

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
| No entran logs del generator | El driver de logging no se aplicó | `docker compose up -d --force-recreate order-generator` |
| Logstash no arranca | Error de sintaxis en el `.conf` | `docker compose logs logstash --tail 40` |
| `docker compose config` da error | La indentación del bloque `logging:` | Va con **4 espacios**, al mismo nivel que `depends_on:` |
| El puerto 5000 no aparece en `docker compose ps` | Falta el `/udp` al final | Revisa el Paso 3 |
| `_count` de Elasticsearch da 0 | Logstash aún no arrancó | Espera 60 s; Logstash tarda |
| Aparece `_grokparsefailure` | El patrón no casa con el texto | Compara el patrón con una línea real |
| Aparece `_dateparsefailure` | Formato de fecha no contemplado | Revisa el bloque `date` del Paso 11 |
| Discover vacío pero `_count` > 0 | Rango de tiempo o Data View | "Last 15 minutes" + Refresh |
| Los logs salen desfasados unos segundos | El filtro `date` no está parseando | Comprueba `_dateparsefailure` |

---

## Antes de la Sesión 4

1. **Baja el stack:** `docker compose down` (sin `-v`).
2. **Lee** `docs/logstash_intro.md`. Repasa lo de hoy y prepara lo de la próxima.
3. **Completa el entregable** con la plantilla `scripts/entregable_template.md`.

> Con esto termina el Capítulo 1: ya sabes **capturar** métricas y logs. El
> Capítulo 2 empieza por hacerlos visibles. En la Sesión 4 se llena la segunda
> caja: Grafana.
