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

> **Cómo copiar los comandos de este manual.** Los bloques de varias líneas se
> pegan **enteros de una vez**, no línea a línea. Si al pegar aparece un `>>` y la
> consola se queda esperando, es que el comando quedó a medias: pulsa `Ctrl+C` y
> vuelve a pegarlo completo.

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
{"timestamp":"2026-08-12 03:12:15,842","level":"INFO","service":"processor","message":"Order processed","event":"order_processed","order_id":"2a008396-53f6-4ac2-9eee-6d193f9c33cb","region":"lima","total_amount":127.5}
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

> **Fíjate en los dos identificadores: no son iguales.** El processor escribe el
> UUID completo (`2a008396-53f6-4ac2-9eee-6d193f9c33cb`) y el generator solo sus
> ocho primeros caracteres (`id=2a008396`). Por eso el campo que extraerás con
> grok se llamará `order_id_short`: **no se pueden cruzar los dos orígenes con una
> búsqueda de `order_id` a secas**. Para seguir una orden por los dos flujos hay
> que buscar por el prefijo.

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
    # servicio de Compose como "logstash". Se usa la direccion numerica
    # 127.0.0.1, no el nombre "localhost": ver la nota de abajo.
    logging:
      driver: syslog
      options:
        syslog-address: "udp://127.0.0.1:${LOGSTASH_SYSLOG_PORT:-5000}"
        tag: "order-generator"
```

Con eso, **Docker intercepta todo lo que el contenedor escribe** en su salida
estándar y lo reenvía por syslog.

> **La línea que confunde a todo el mundo: ¿por qué no `logstash`?**
>
> Porque el driver de logging **no corre dentro del contenedor**: corre en el
> demonio de Docker, fuera de la red de Compose. Ahí `logstash` no significa nada,
> porque el DNS interno de Compose no existe. Pero el puerto 5000 está publicado
> en la máquina, y el demonio sí lo alcanza por su dirección local.

> **Y la segunda pregunta: ¿por qué `127.0.0.1` y no `localhost`?**
>
> Porque **`localhost` no funciona aquí**, y falla de la peor manera posible: sin
> decir nada.
>
> Dentro de la máquina virtual de Docker, el nombre `localhost` está asociado a
> **dos** direcciones: `127.0.0.1` (IPv4) y `::1` (IPv6). Es como un contacto con
> dos números de teléfono. El driver, escrito en Go, prefiere el moderno y marca
> `::1`. Pero Logstash escucha en `0.0.0.0:5000`, que es **solo IPv4**: nadie
> contesta en ese número.
>
> Y como syslog viaja por **UDP**, el mensaje se pierde sin acuse de recibo. Ni un
> error, ni un aviso, ni una línea en ningún log. Solo un contador que no sube.
>
> Escribiendo la dirección numérica no hay nada que traducir, y no hay ambigüedad
> posible.

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

**Comprueba que se guardó.** No sigas sin hacerlo:

```powershell
Select-String "LOGSTASH_SYSLOG_PORT" .env
```

Tiene que devolverte la línea. Si no devuelve nada, el editor no guardó el archivo:
pulsa `Ctrl+S` y repite.

> **Por qué insistimos en esto.** Un archivo editado y sin guardar no falla donde lo
> editaste: falla tres pasos más adelante, cuando ya no lo relacionas con esta
> edición y te pones a buscar el problema en otro sitio. Haz esta comprobación
> después de **cada** cambio de archivo de la sesión.

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

> **Windows en español:** el Explorador muestra la carpeta como «Descargas», pero
> su nombre real en disco sigue siendo `Downloads`. Ese «Descargas» es solo una
> etiqueta que Windows enseña. Si escribes `$HOME\Descargas` obtendrás un error de
> ruta inexistente.

**Comprueba que se copió el archivo correcto:**

```powershell
Select-String "syslog" .\logstash\pipeline\orderflow.conf
```

**Qué debes ver:** varias líneas mencionando `syslog`. Si no aparece ninguna, sigues
teniendo el pipeline de la Sesión 1 y la copia no se hizo.

Y comprueba que tus ediciones del YAML son válidas:

```bash
docker compose config --services
```

**Qué debes ver:** los 13 nombres de siempre, sin errores de sintaxis.

> **Cuidado con lo que comprueba cada cosa.** `docker compose config` lee
> **únicamente** el `docker-compose.yml`: valida los cambios que hiciste en los
> pasos 3 y 4. **No abre el pipeline de Logstash**, así que da exactamente la misma
> salida aunque el `.conf` esté mal copiado o incluso borrado. Por eso hacen falta
> las dos comprobaciones, y no una.
>
> No verifiques la copia contando líneas: el número depende del comando que uses
> (`Measure-Object -Line` no cuenta las líneas en blanco, y este archivo tiene
> catorce). Comprobar que el contenido es el esperado es más fiable que contar.

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

> **A partir de ahora, `docker compose logs order-generator` no devuelve nada.**
> Y es lo correcto, no un fallo. Con el driver `syslog`, Docker ya no guarda una
> copia local de los logs: los reenvía y se desentiende. El comando responde vacío,
> sin error y con código de salida 0.
>
> El generator sigue perfectamente vivo. Si quieres comprobarlo, míralo por otro
> lado — sus métricas, que no pasan por los logs:
>
> ```powershell
> (Invoke-WebRequest "http://localhost:8000/metrics" -UseBasicParsing).Content -split "`n" | Select-String "^orderflow_orders_generated_total"
> ```
>
> A partir de hoy, el generator se observa desde Kibana o desde sus métricas. Es el
> precio de haber redirigido sus logs, y conviene saberlo antes de necesitarlo.

### Paso 8 — Verificar que los dos flujos llegan

**Primero, que Logstash haya arrancado del todo.** Tarda cerca de un minuto: por
dentro levanta una máquina virtual de Java. Espera y luego mira:

```bash
docker compose logs logstash --tail 30
```

**Qué debes ver**, y esto es lo que confirma que tu `.conf` funciona:

```
Starting syslog udp listener {:address=>"0.0.0.0:5000"}
Starting syslog tcp listener {:address=>"0.0.0.0:5000"}
Starting tcp input listener  {:address=>"0.0.0.0:5044"}
Pipeline started
```

Tres puertas abiertas: la de siempre (5044) y **dos nuevas** en el 5000. Escribiste
un solo puerto y el plugin syslog abrió TCP y UDP por su cuenta.

> **Dos avisos amarillos que son normales** y aparecen en todos los arranques:
> `Restored connection to ES instance` (Logstash arranca antes que Elasticsearch,
> reintenta y lo encuentra: no se cayó nada) y `Detected a 6.x and above cluster`
> (aviso de compatibilidad hacia atrás). Ninguno de los dos es un problema.

> **No midas nada hasta ver esas líneas.** Mientras Logstash arranca, el puerto 5000
> todavía no existe, y todo lo que el generator envíe en ese rato **se pierde**: UDP
> no encola ni reintenta. Si mides demasiado pronto verás cero y parecerá que algo
> está mal.

**Ahora la prueba contra Elasticsearch.** Y no basta con contar el total: a ese
índice llegan **dos** flujos, así que hay que comprobarlos **por separado**. Si uno
está mudo y el otro trabaja, el total sube igual y no te enteras.

En **PowerShell**:

```powershell
Invoke-RestMethod "http://localhost:9200/orderflow-logs-*/_count?q=tags:processor"
Invoke-RestMethod "http://localhost:9200/orderflow-logs-*/_count?q=tags:generator"
```

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
curl -s "http://localhost:9200/orderflow-logs-*/_count?q=tags:processor"
curl -s "http://localhost:9200/orderflow-logs-*/_count?q=tags:generator"
```

</details>

**Qué debes ver:** los dos con `count` mayor que cero. Pero un número aislado no
prueba nada — puede ser histórico. Lo que importa es que **crezca**:

```powershell
$a = (Invoke-RestMethod "http://localhost:9200/orderflow-logs-*/_count?q=tags:generator").count; Start-Sleep -Seconds 30; $b = (Invoke-RestMethod "http://localhost:9200/orderflow-logs-*/_count?q=tags:generator").count; "generator: $a -> $b   (diferencia: $($b - $a))"
```

**Qué debes ver:** una diferencia de unos **30**. El generator produce una orden por
segundo, así que en treinta segundos deben entrar treinta documentos.

> **Si la diferencia es 0**, los logs no están llegando. Repasa en este orden: que
> Logstash haya terminado de arrancar (arriba), que el Paso 4 diga `127.0.0.1` y no
> `localhost`, y que el Paso 5 esté guardado en el `.env`.

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

El input `syslog` lleva además una tercera línea:

```ruby
grok_pattern => "<%{POSINT:priority}>%{SYSLOGTIMESTAMP:timestamp} %{SYSLOGPROG}: %{GREEDYDATA:message}"
```

> **Por qué hace falta.** El formato syslog estándar exige cinco piezas: prioridad,
> fecha, **nombre de la máquina**, programa y mensaje. El driver de Docker emite
> solo cuatro: **se salta el nombre de la máquina**. Logstash, que espera la
> plantilla completa, no encuentra encaje y guarda el mensaje entero sin procesar.
>
> Las consecuencias son llamativas: la prioridad se queda en 0, que significa
> «emergencia del kernel», y **todos tus logs de negocio aparecen catalogados como
> la máxima urgencia del sistema operativo**. Además el sobre —ese `<30>Aug 31
> 04:22:24 order-generator[111]:` del principio— se queda pegado dentro del mensaje.
>
> Esta línea le dice a Logstash cuál es el formato que Docker manda **de verdad**.
> Con ella, la prioridad se lee bien (`Informational`, no `Emergency`), el sobre se
> descarta y aparecen dos campos nuevos: `program` y `pid`.

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

Son **tres** etiquetas, no dos. En **PowerShell**:

```powershell
"grok filtro :"; (Invoke-RestMethod "http://localhost:9200/orderflow-logs-*/_count?q=tags:_grokparsefailure").count
"grok syslog :"; (Invoke-RestMethod "http://localhost:9200/orderflow-logs-*/_count?q=tags:_grokparsefailure_sysloginput").count
"fecha       :"; (Invoke-RestMethod "http://localhost:9200/orderflow-logs-*/_count?q=tags:_dateparsefailure").count
```

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
curl -s "http://localhost:9200/orderflow-logs-*/_count?q=tags:_grokparsefailure"
curl -s "http://localhost:9200/orderflow-logs-*/_count?q=tags:_grokparsefailure_sysloginput"
curl -s "http://localhost:9200/orderflow-logs-*/_count?q=tags:_dateparsefailure"
```

</details>

**Qué debes ver:** `0` en las tres.

> **Las dos primeras se parecen pero no son la misma.** `_grokparsefailure` la pone
> el **filtro** grok, el del Paso 10. `_grokparsefailure_sysloginput` la pone la
> **puerta de entrada** syslog, que hace su propio parseo antes de que el filtro
> exista. Son dos sitios distintos y cada uno firma con su nombre.
>
> Si preguntas solo por la primera, puedes obtener un tranquilizador `0` mientras
> **todos** los eventos del generator están fallando en la segunda. Buscar «Pérez»
> no encuentra al fichado como «Pérez-Gómez».

**Y ahora lo más importante del paso: abre un documento y míralo por dentro.**

```powershell
(Invoke-RestMethod "http://localhost:9200/orderflow-logs-*/_search?q=tags:generator&size=1&sort=@timestamp:desc").hits.hits._source | ConvertTo-Json -Depth 4
```

**Qué debes ver:** `severity_label` en `Informational` (no `Emergency`),
`facility_label` en `system` (no `kernel`), el `message` limpio y sin la cabecera
`<30>...` pegada delante, y los campos `region`, `items_count` y `total_amount` que
fabricó grok.

> **Por qué este paso vale más que los contadores.** Un contador a cero no demuestra
> que todo esté bien: demuestra que **no encontró lo que estaba buscando**. Y a veces
> no lo encontró porque preguntaba por el nombre equivocado. Mirar un documento real
> es la única comprobación que no se puede engañar a sí misma. Hazlo siempre.

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
   increase(orderflow_orders_failed_total[1h])
   ```

   Anota **qué causa** tiene el valor más alto.

   > **Saldrán decimales**, del tipo `49.7`. ¿Cómo van a fallar 49,7 órdenes? No
   > fallaron: Prometheus **no cuenta, estima**. Toma la primera y la última medida
   > de la ventana y calcula la pendiente entre ellas. Es un cálculo estadístico,
   > no un recuento.

2. En **Kibana**, con el rango de tiempo en **la última hora**, busca esa misma
   causa:

   ```
   event: "order_failed" and reason: "TU_CAUSA_AQUI"
   ```

3. Abre uno de los documentos (flecha a la izquierda de la fila) y localiza el
   `order_id` concreto.

> **Compara la causa dominante, no la lista entera.** Prometheus estima pendientes
> y los logs cuentan documentos: son dos formas distintas de medir, y sus números
> **no van a coincidir**, ni falta que hace. En ventanas cortas, además, el orden de
> las causas menos frecuentes cambia solo de una medición a otra: con veinte sucesos,
> una diferencia de dos es azar.
>
> Lo que importa es que la causa **más frecuente** sea la misma en los dos sitios.
> Eso demuestra que las dos herramientas ven la misma realidad. Que los números
> difieran demuestra que la miden de forma distinta, que es exactamente lo que
> tienen que hacer.

> **Y si comparas cantidades entre sí, mídelas en la misma consulta.** Varias
> consultas seguidas son fotos de instantes distintos: restarlas entre sí no
> significa nada, porque la ventana `now-1h` se ha desplazado entre una y otra.

Acabas de recorrer el camino completo: **la métrica te dijo que había un problema
y cuál era el más frecuente; el log te dijo exactamente qué orden lo sufrió y
cuándo.** Ninguna de las dos herramientas podía darte eso sola.

---

## Ejercicios (haz estos tú solo)

### Ejercicio A — ¿Hay alguna región que destaque?

Usando Kibana, averigua **qué región genera más órdenes** en la última hora, y
**cuál tiene el ticket medio más alto**. Después responde: ¿hay alguna que se salga
de lo normal, o están todas equilibradas? Justifica la respuesta.

*Pista: filtra por `tags: "generator"`, busca el campo `region` en el panel
izquierdo y pulsa **Visualize**. Para el ticket medio, cambia la métrica de
«Count» a «Average» sobre `total_amount`.*

> **Una advertencia que te ahorrará tiempo.** Podrías pensar en resolverlo sobre
> los eventos `order_failed`. No se puede: **esos eventos no tienen campo `region`**.
> El processor recibe la orden desde la cola y solo maneja su identificador; la
> región la conoce quien la creó, que es el generator. Comprobarlo es fácil y es
> buena costumbre antes de dar nada por hecho:
>
> ```powershell
> Invoke-RestMethod "http://localhost:9200/orderflow-logs-*/_count?q=event:order_failed%20AND%20_exists_:region"
> ```
>
> Ese `_exists_` pregunta si el campo existe en el documento. Devuelve 0.

> **Fíjate en lo que estás consultando.** El campo `region` **no venía** en los logs
> del generator: era una tira de texto. Lo creaste tú con grok hace veinte minutos.
> Estás haciendo análisis de negocio sobre unos logs que nacieron sin saber lo que
> era una región.

### Ejercicio B — Generadas contra procesadas

Con el rango de tiempo en **los últimos 5 minutos**, escribe **tres** consultas KQL
y anota los tres números: `event: "order_generated"`, `event: "order_processed"` y
`event: "order_failed"`.

Después responde: ¿cuadra la cuenta? Explica en dos líneas dónde está la diferencia.

> **Por qué cinco minutos y no «la última hora».** Los dos flujos no llevan el mismo
> tiempo funcionando: el processor manda logs desde la Sesión 1 y el generator desde
> hace un rato, cuando abriste el camino syslog. En ventanas largas los números no
> son comparables y la conclusión sale disparatada. Elige siempre una ventana en la
> que las dos cosas que comparas hayan estado activas por igual.

> **Y por qué hacen falta las tres consultas.** Con solo dos, la cuenta parece no
> cuadrar y es fácil concluir «se pierden órdenes», que es falso. Una orden que falla
> **no desaparece**: quedó registrada como fallida. Súmalas antes de comparar.

### Ejercicio C — Mejorar una extracción que ya existe

Abre el pipeline y busca cómo se obtiene el campo `level` de los logs del generator.
Verás que **no** se usa grok, sino tres condicionales que buscan la palabra suelta
dentro del texto, con un `else` que asigna `INFO` a todo lo demás.

Ese código tiene dos defectos y deja un dato sin aprovechar. Encuéntralos y propón
(solo escríbelo, no hace falta aplicarlo) el bloque que lo sustituiría, usando grok
sobre el principio de la línea:

```
2026-08-12 03:12:15,481 INFO - Order generated: ...
```

*Pistas: existe un patrón predefinido llamado `TIMESTAMP_ISO8601` y otro llamado
`LOGLEVEL`. El símbolo `^` ancla un patrón al inicio de la línea. Y compara el
`@timestamp` de un documento con la hora que aparece dentro de su `message`:
fíjate en los milisegundos.*

> **Una pista más para el segundo defecto.** Pregúntate qué le pasaría a un log de
> nivel `CRITICAL` con el código actual. ¿Se vería? ¿Cómo se guardaría?

---

## Si algo falla

| Síntoma | Causa probable | Solución |
|---|---|---|
| Cualquier comando `docker` falla mencionando `dockerDesktopLinuxEngine` | Docker Desktop no está en marcha | Ábrelo y espera a que la ballena deje de moverse. El comando no tiene nada de malo |
| El contador del generator no sube | El Paso 4 dice `localhost` en vez de `127.0.0.1` | Corrígelo y **recrea**: `docker compose up -d --force-recreate order-generator` |
| El contador del generator no sube, y el Paso 4 está bien | Logstash todavía está arrancando | Espera a ver `Starting syslog udp listener` en sus logs y vuelve a medir |
| No entran logs del generator | El driver de logging no se aplicó | `docker compose up -d --force-recreate order-generator` |
| `docker compose logs order-generator` no devuelve nada | **Es lo esperado** desde el Paso 7 | Comprueba el generator en Kibana o en `localhost:8000/metrics` |
| Logstash no arranca | Error de sintaxis en el `.conf` | `docker compose logs logstash --tail 40` |
| `docker compose config` da error | La indentación del bloque `logging:` | Va con **4 espacios**, al mismo nivel que `depends_on:` |
| El puerto 5000 no aparece en `docker compose ps` | Falta el `/udp` al final | Revisa el Paso 3 |
| `_count` de Elasticsearch da 0 | Logstash aún no arrancó | Espera 60 s; Logstash tarda |
| Aparece `_grokparsefailure` | El patrón del filtro no casa con el texto | Compara el patrón con una línea real |
| Aparece `_grokparsefailure_sysloginput` | Falta el `grok_pattern` en el input syslog | Revisa el Paso 9: Docker emite syslog sin nombre de máquina |
| Aparece `_dateparsefailure` | Formato de fecha no contemplado | Revisa el bloque `date` del Paso 11 |
| Discover vacío pero `_count` > 0 | Rango de tiempo o Data View | "Last 15 minutes" + Refresh |
| Los logs salen desfasados unos segundos | El filtro `date` no está parseando | Comprueba `_dateparsefailure` |
| Un cambio en un archivo no surte efecto | El editor no lo guardó | `Select-String "loQueAñadiste" elArchivo`. Si no devuelve nada, falta `Ctrl+S` |
| Al pegar un comando aparece `>>` y no pasa nada | El bloque se pegó a medias | `Ctrl+C` y pégalo entero de una vez |

---

## Antes de la Sesión 4

1. **Baja el stack:** `docker compose down` (sin `-v`).
2. **Lee** `docs/logstash_intro.md`. Repasa lo de hoy y prepara lo de la próxima.
3. **Completa el entregable** con la plantilla `scripts/entregable_template.md`.

> Con esto termina el Capítulo 1: ya sabes **capturar** métricas y logs. El
> Capítulo 2 empieza por hacerlos visibles. En la Sesión 4 se llena la segunda
> caja: Grafana.
