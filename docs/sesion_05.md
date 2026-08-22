# Manual de práctica — Sesión 5

## Alertas y notificaciones operativas

**Capítulo 2:** Dashboards, alertas e integración aplicada

> Las diapositivas explican la teoría; los comandos y las consultas salen de aquí.
> Si una consulta de la pantalla no coincide con este documento, manda este documento.

---

## Qué vas a construir hoy

Hoy **se llena la tercera y última caja vacía**: Alertmanager.

Hasta ahora, para enterarte de que OrderFlow va mal tenías que estar mirando.
Al terminar la sesión el sistema te avisa solo, y tú vas a haber visto una
alerta recorrer entera su vida: métrica → regla → `pending` → `firing` →
notificación → `resolved`.

El stack crece de 13 a **15 servicios**. Los dos nuevos existen para que puedas
ver una notificación real sin cuenta de correo y sin salir a internet.

Al terminar serás capaz de:

- Escribir reglas de alerta en Prometheus con umbral, `for`, labels y anotaciones.
- Configurar el enrutamiento de Alertmanager: agrupación, receptores e inhibición.
- Provocar un incidente controlado y seguirlo hasta la notificación.
- Silenciar una alerta durante un mantenimiento.

---

## Punto de partida

Necesitas dos cosas:

1. El stack de la Sesión 4 funcionando, con tu dashboard en
   `grafana/dashboards/orderflow-overview.json`.
2. Los **cuatro archivos** que descargaste de la plataforma: `app.py`,
   `Dockerfile`, `requirements.txt` y `orderflow-alerts.yml`.

### Paso 1 — Crear el microservicio que recibe las alertas

El `webhook-receiver` es un servicio Flask de 80 líneas. Te lo damos hecho: hoy
lo importante es **ver el JSON real de una alerta**, no escribir Python.

Crea su carpeta y copia dentro los tres archivos:

**Windows (PowerShell):**
```powershell
New-Item -ItemType Directory -Force -Path services\webhook-receiver
Copy-Item "$HOME\Downloads\app.py","$HOME\Downloads\Dockerfile","$HOME\Downloads\requirements.txt" services\webhook-receiver\
```

**Mac/Linux:**
```bash
mkdir -p services/webhook-receiver
cp ~/Downloads/{app.py,Dockerfile,requirements.txt} services/webhook-receiver/
```

Comprueba que están los tres:

```bash
ls services/webhook-receiver
```

### Paso 2 — Instalar la alerta de Grafana

Este archivo lo mirarás al final de la sesión, para comparar dos formas de
escribir la misma alerta.

**Windows (PowerShell):**
```powershell
New-Item -ItemType Directory -Force -Path grafana\provisioning\alerting
Copy-Item "$HOME\Downloads\orderflow-alerts.yml" grafana\provisioning\alerting\
```

**Mac/Linux:**
```bash
mkdir -p grafana/provisioning/alerting
cp ~/Downloads/orderflow-alerts.yml grafana/provisioning/alerting/
```

### Paso 3 — Añadir los dos servicios al stack

Abre `docker-compose.yml` y baja **al final del archivo**. Pega este bloque:

```yaml
  # ============================================================
  # DESTINOS DE NOTIFICACION (anadidos en la Sesion 5)
  # ============================================================
  # Alertmanager ya estaba desde la Sesion 1, pero sin nadie a quien
  # avisar. Estos dos servicios son ese "alguien": permiten ver una
  # notificacion real sin cuenta de correo, sin SMTP externo y sin
  # salir a internet.
  # ============================================================

  # Buzon SMTP de mentira. Acepta cualquier correo que le manden y lo
  # muestra en una interfaz web en el puerto 8025, sin entregarlo a
  # nadie. Es el estandar para probar envios de correo en desarrollo.
  mailhog:
    image: mailhog/mailhog:v1.0.1
    container_name: orderflow-mailhog
    restart: unless-stopped
    ports:
      - "${MAILHOG_UI_PORT:-8025}:8025"
      - "${MAILHOG_SMTP_PORT:-1025}:1025"
    networks:
      - orderflow-net

  # Microservicio Flask que recibe el POST de Alertmanager y lo
  # imprime formateado. Sirve para VER el JSON real de una alerta,
  # que es lo que recibiria Slack, PagerDuty o un sistema de tickets.
  webhook-receiver:
    build:
      context: ./services/webhook-receiver
      dockerfile: Dockerfile
    container_name: orderflow-webhook-receiver
    restart: unless-stopped
    ports:
      - "${WEBHOOK_PORT:-5001}:5001"
    networks:
      - orderflow-net
```

> **`image:` contra `build:`.** MailHog usa una imagen que ya existe en Docker
> Hub. El `webhook-receiver` no: su código es tuyo, está en la carpeta que
> acabas de crear, y Docker tiene que **construir** la imagen a partir del
> `Dockerfile`. Por eso el comando de levantado de hoy lleva `--build`.

### Paso 4 — Declarar los puertos en tu `.env`

Abre `.env` y añade al final:

```
# --- Destinos de notificacion (anadidos en la Sesion 5) ---
# MailHog: buzon SMTP de prueba. 8025 es la interfaz web donde se leen
# los correos; 1025 es el puerto SMTP al que escribe Alertmanager.
MAILHOG_UI_PORT=8025
MAILHOG_SMTP_PORT=1025
# webhook-receiver: microservicio que imprime el JSON de la alerta.
WEBHOOK_PORT=5001
```

### Paso 5 — Levantar

```bash
docker compose up -d --build
```

La primera vez tarda ~40 segundos: Docker descarga MailHog y construye la imagen
del webhook.

**Paso 6.** Comprueba que ahora son 15:

```bash
docker compose ps --format "table {{.Name}}\t{{.Status}}"
```

En PowerShell funciona igual.

**Paso 7.** Confirma que los dos nuevos responden:

```powershell
Invoke-RestMethod http://localhost:5001/health
```

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
curl -s http://localhost:5001/health
```

</details>

Debe devolver `{"status":"up"}`.

Y abre `http://localhost:8025` en el navegador: es MailHog, un buzón de correo
vacío. Al final de la sesión tendrá dentro un correo que nadie escribió a mano.

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

## Bloque 1 — Las reglas: qué vigila Prometheus

**Paso 8.** Abre `prometheus/alerts.yml`. Hoy dice esto:

```yaml
groups: []
```

Ésa es la razón de que Alertmanager lleve cuatro sesiones sin recibir nada. Vamos
a llenarlo.

**Borra todo el contenido del archivo** y pega esto en su lugar:

```yaml
# ============================================================
# Prometheus - Reglas de alerta
# ============================================================
# LOS NOMBRES DE METRICA NO SE ADIVINAN. Todos los que aparecen aqui
# estan en docs/metricas.md y se pueden comprobar uno a uno en
# http://localhost:8001/metrics. Una regla con un nombre inexistente
# no da error: simplemente no dispara nunca, que es la peor forma de
# fallar que puede tener una alerta.
# ============================================================

groups:

  # ----------------------------------------------------------
  # Grupo 1: disponibilidad de los servicios
  # ----------------------------------------------------------
  # 'up' es una metrica que genera el propio Prometheus por cada
  # target: vale 1 si el ultimo scrape funciono, 0 si no. No hay que
  # instrumentar nada para tenerla.
  - name: orderflow_disponibilidad
    rules:

      - alert: ProcessorCaido
        expr: up{job="order-processor"} == 0
        for: 1m
        labels:
          severity: critical
          service: order-processor
        annotations:
          summary: "El order-processor esta caido"
          description: >-
            Prometheus no logra scrapear el order-processor
            (instancia {{ $labels.instance }}) desde hace mas de 1 minuto.

      - alert: GeneratorCaido
        expr: up{job="order-generator"} == 0
        for: 1m
        labels:
          severity: warning
          service: order-generator
        annotations:
          summary: "El order-generator esta caido"
          description: >-
            El generador de ordenes no responde al scraping desde hace
            mas de 1 minuto. El pipeline dejara de recibir ordenes nuevas.

  # ----------------------------------------------------------
  # Grupo 2: salud del procesamiento
  # ----------------------------------------------------------
  - name: orderflow_procesamiento
    rules:

      # Porcentaje de ordenes fallidas en los ultimos 5 minutos.
      # Es la misma expresion del panel "Tasa de error %" de la
      # Sesion 4: el dashboard y la alerta miran exactamente lo mismo,
      # y eso es deliberado. Si difirieran, el grafico diria una cosa
      # y el correo otra.
      - alert: TasaErrorAlta
        expr: >-
          100 *
          sum(rate(orderflow_orders_failed_total[5m]))
          /
          clamp_min(
            sum(rate(orderflow_orders_processed_total[5m]))
            + sum(rate(orderflow_orders_failed_total[5m])),
            0.001
          )
          > 10
        # 'for' es lo que separa una alerta util de una molesta: la
        # condicion tiene que mantenerse 2 minutos seguidos. Un pico
        # de 10 segundos no despierta a nadie.
        for: 2m
        labels:
          severity: critical
          service: order-processor
        annotations:
          summary: "Tasa de error de procesamiento por encima del 10%"
          description: >-
            La proporcion de ordenes fallidas es {{ printf "%.1f" $value }}%
            en los ultimos 5 minutos (umbral: 10%).

      # P95 de la latencia por encima de 1 segundo.
      # Igual que en Grafana: el nombre termina en _bucket y el
      # sum() conserva la etiqueta le. Sin esas dos cosas, la
      # expresion devuelve NaN y la alerta jamas dispara.
      - alert: LatenciaAltaP95
        expr: >-
          histogram_quantile(
            0.95,
            sum by (le) (rate(orderflow_processing_duration_seconds_bucket[5m]))
          ) > 1
        for: 5m
        labels:
          severity: warning
          service: order-processor
        annotations:
          summary: "Latencia p95 de procesamiento elevada"
          description: >-
            El percentil 95 de la latencia de procesamiento es
            {{ printf "%.2f" $value }}s (umbral: 1s) durante los ultimos 5 min.

      # ------------------------------------------------------
      # TODO (Sesion 5) - Escribe tu la cuarta regla.
      # ------------------------------------------------------
      # Nombre:    SinOrdenesProcesadas
      # Condicion: no se ha procesado NINGUNA orden en los ultimos
      #            10 minutos. Es un atasco: el generator sigue
      #            produciendo, pero nada sale por el otro lado.
      # for:       10m
      # severity:  warning
      # service:   order-processor
      #
      # Pista: la tasa de un counter durante una ventana en la que no
      # paso nada vale exactamente 0. Necesitas sum(rate(...[10m]))
      # y compararlo con 0.
      #
      # El nombre de la metrica esta en docs/metricas.md.
      # Cuando termines, recarga Prometheus:
      #   Invoke-RestMethod -Method Post http://localhost:9090/-/reload
      # ------------------------------------------------------
```

Guarda con `Ctrl+S`. **Ese `TODO` del final es el Ejercicio B**: lo escribirás tú
más tarde.

**Paso 9.** Ahora que lo tienes delante, fíjate en la anatomía de
`TasaErrorAlta`, porque las cuatro partes hacen cosas distintas:

| Parte | Qué hace |
|---|---|
| `expr` | La condición PromQL. Mientras devuelva resultado, la alerta está activa |
| `for` | Cuánto debe mantenerse antes de disparar de verdad |
| `labels` | Clasifican la alerta. `severity` y `service` deciden a quién se avisa |
| `annotations` | El texto que lee la persona. Admite `{{ $value }}` y `{{ $labels.x }}` |

El `for: 2m` es lo que separa una alerta útil de una que nadie mira. Sin él, un
pico de 10 segundos manda un correo. Con él, hay que estar roto dos minutos
seguidos.

> **La expresión de la alerta es la misma del panel de la Sesión 4.** No es
> casualidad. Si el dashboard mide la tasa de error de una forma y la alerta de
> otra, llega el día en que el gráfico está verde y el correo dice que todo arde.
> Nadie sabe a cuál creerle.

**Paso 10.** Comprueba que Prometheus sabe a quién avisar. Abre
`prometheus/prometheus.yml` y localiza estos dos bloques, que están ahí desde la
Sesión 1:

```yaml
alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]

rule_files:
  - /etc/prometheus/alerts.yml
```

Sin `alerting`, Prometheus detectaría el problema y no se lo contaría a nadie.

**Paso 11.** Recarga Prometheus sin reiniciarlo:

```powershell
Invoke-RestMethod -Method Post http://localhost:9090/-/reload
```

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
curl -X POST http://localhost:9090/-/reload
```

</details>

Esto funciona porque el contenedor arranca con `--web.enable-lifecycle`. Sin ese
flag habría que reiniciar Prometheus y perderías el buffer de métricas en curso.

**Paso 12.** Ve a `http://localhost:9090/alerts`.

Verás tus reglas agrupadas, todas en verde y en estado **Inactive**. Todavía no
pasa nada malo. Eso es exactamente lo que debe verse en un sistema sano.

> **Si no aparece ninguna regla**, el YAML tiene un error de sintaxis y
> Prometheus rechazó el archivo entero:
> `docker compose logs prometheus --tail 30`

---

## Bloque 2 — Alertmanager: a quién se avisa

Prometheus **detecta**. Alertmanager **decide** a quién avisar, cuándo y cuántas
veces. Son dos trabajos distintos y por eso son dos programas distintos.

**Paso 13.** Abre `alertmanager/alertmanager.yml`. Lo que hay es un receptor
vacío: Alertmanager arranca, pero no avisa a nadie.

**Borra todo el contenido** y pega esto:

```yaml
# ============================================================
# Alertmanager - Configuracion de OrderFlow
# ============================================================
# Recargar sin reiniciar:
#   Invoke-RestMethod -Method Post http://localhost:9093/-/reload
# ============================================================

global:
  # Cuanto espera antes de dar una alerta por resuelta si deja de
  # recibir noticias de ella.
  resolve_timeout: 5m

  # SMTP de MailHog, el buzon de mentira que anadiste al compose en
  # el Paso 3. No pide usuario, ni contrasena, ni TLS: por eso
  # sirve para clase. En produccion aqui irian credenciales reales.
  smtp_smarthost: 'mailhog:1025'
  smtp_from: 'alertmanager@orderflow.local'
  smtp_require_tls: false

# ------------------------------------------------------------
# Arbol de enrutamiento: que receiver atiende cada alerta.
# ------------------------------------------------------------
route:
  receiver: 'equipo-datos-email'

  # Agrupa en una sola notificacion las alertas que comparten estas
  # etiquetas. Sin group_by, 40 ordenes fallando podrian generar 40
  # correos. Con el, generan uno.
  group_by: ['alertname', 'service']

  # Espera antes del primer aviso de un grupo nuevo: da margen a que
  # lleguen alertas hermanas y viajen juntas.
  group_wait: 30s
  # Espera antes de avisar de cambios dentro de un grupo ya notificado.
  group_interval: 5m
  # Cada cuanto se repite el aviso de algo que sigue roto.
  repeat_interval: 3h

  routes:
    # Lo critico va al webhook, que es el canal urgente, y se repite
    # cada hora en vez de cada tres.
    - receiver: 'guardia-webhook'
      matchers:
        - severity="critical"
      group_wait: 10s
      repeat_interval: 1h
      # continue: true hace que la alerta siga evaluandose contra las
      # rutas hermanas despues de coincidir aqui. Sin esto, una alerta
      # critica llegaria al webhook y a ningun sitio mas.
      continue: true

    # Ruta final sin matchers: casa con todo lo que llegue hasta aqui.
    # Las alertas warning e info caen directamente. Las criticas caen
    # tambien, porque la ruta anterior las dejo continuar.
    #
    # Ojo con este detalle: si esta ruta llevara matchers de
    # warning|info, una alerta critica no casaria con ninguna ruta
    # hermana despues de la primera y jamas llegaria al correo. Es un
    # fallo silencioso clasico de Alertmanager.
    - receiver: 'equipo-datos-email'

# ------------------------------------------------------------
# Receivers: a donde se envia cada notificacion.
# ------------------------------------------------------------
receivers:
  - name: 'equipo-datos-email'
    email_configs:
      - to: 'equipo-datos@orderflow.local'
        # Tambien avisa cuando la alerta se resuelve. Enterarse de
        # que algo volvio a la normalidad es tan util como enterarse
        # de que se rompio.
        send_resolved: true

  - name: 'guardia-webhook'
    webhook_configs:
      # webhook-receiver es el nombre del servicio en docker-compose.yml.
      # Dentro de la red de Compose ese nombre resuelve solo: no hace
      # falta IP ni localhost.
      - url: 'http://webhook-receiver:5001/alertas'
        send_resolved: true

# ------------------------------------------------------------
# Inhibicion: callar el ruido durante un incidente.
# ------------------------------------------------------------
# Si el processor esta caido (critical), la alerta de latencia alta
# del mismo servicio (warning) no aporta nada: es una consecuencia,
# no una causa. Esta regla la silencia mientras dure la critica.
inhibit_rules:
  - source_matchers:
      - severity="critical"
    target_matchers:
      - severity="warning"
    # Solo inhibe entre alertas del MISMO servicio. Sin este equal,
    # una critica de Postgres silenciaria los avisos de Redis.
    equal: ['service']
```

Guarda con `Ctrl+S`.

**Paso 14.** Tres mecanismos que acabas de configurar y conviene entender:

**Agrupación.** `group_by: ['alertname', 'service']` junta en un solo aviso todas
las alertas que comparten nombre y servicio. Sin esto, cuarenta órdenes fallando
podrían producir cuarenta correos.

**Enrutamiento.** El árbol se recorre de arriba abajo. Lo `critical` va al
webhook con `group_wait: 10s` —más urgente— y lleva `continue: true`, que le
permite seguir bajando y caer también en la ruta final, la del correo. Lo demás
solo llega al correo.

> Fíjate en que la ruta final **no tiene `matchers`**. Ese detalle importa: si
> llevara `severity=~"warning|info"`, una alerta crítica no casaría con ninguna
> ruta después de la primera y nunca llegaría al correo. Es un fallo silencioso
> clásico: la configuración es válida, Alertmanager arranca sin quejarse, y
> media notificación desaparece.

**Inhibición.** Si el processor está caído, la alerta de latencia alta del mismo
servicio sobra: es una consecuencia, no una causa. El bloque `inhibit_rules` la
silencia mientras dure la crítica. El `equal: ['service']` es lo que evita que
una crítica de Postgres silencie los avisos de Redis.

**Paso 15.** Recarga Alertmanager y comprueba que leyó la configuración nueva:

```powershell
Invoke-RestMethod -Method Post http://localhost:9093/-/reload
```

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
curl -X POST http://localhost:9093/-/reload
```

</details>

Abre `http://localhost:9093` → pestaña **Status**. Abajo verás la configuración
activa. Confirma que aparecen los dos receivers: `equipo-datos-email` y
`guardia-webhook`.

---

## Bloque 3 — Provocar un incidente de verdad

Hasta aquí todo es teoría con el sistema sano. Vamos a romperlo a propósito.

**Paso 16.** Deja abierta una terminal mirando el webhook en vivo:

```bash
docker compose logs -f webhook-receiver
```

**Paso 17.** En otra terminal, sube la tasa de error simulada. Edita tu `.env`:

```
ERROR_RATE_PCT=30
```

Estaba en 5. Ahora fallará el 30 % de las órdenes, muy por encima del umbral del
10 % de la regla.

**Paso 18.** Aplica el cambio recreando solo el processor:

```bash
docker compose up -d order-processor
```

**Paso 19.** Ve a `http://localhost:9090/alerts` y refresca cada 20 segundos.

Vas a ver tres estados, en este orden:

1. **Inactive** (verde) — la condición todavía no se cumple. La tasa de error se
   calcula sobre 5 minutos, así que tarda en subir.
2. **Pending** (amarillo) — la condición se cumple, pero no lleva los 2 minutos
   del `for`. Prometheus la está cronometrando.
3. **Firing** (rojo) — aguantó los 2 minutos. Ahora sí se envía a Alertmanager.

Ese paso de amarillo a rojo es el `for` haciendo su trabajo. Ten paciencia: entre
que la ventana de 5 minutos se llena y que pasan los 2 minutos del `for`, pueden
irse 4 o 5 minutos reales.

**Paso 20.** En cuanto esté en **Firing**, mira las dos terminales:

- En `http://localhost:9093` la alerta aparece agrupada por `alertname` y `service`.
- En la terminal del webhook aparece el JSON formateado, con severidad, servicio
  y descripción. **Ese es el payload real** que recibiría Slack o PagerDuty.
- En `http://localhost:8025` hay un correo nuevo.

Nadie escribió ese correo. Lo escribió una regla de nueve líneas.

**Paso 21 — Resolver el incidente.** Devuelve el `.env` a su valor sano:

```
ERROR_RATE_PCT=5
```

```bash
docker compose up -d order-processor
```

Espera unos minutos y vuelve a mirar. La alerta desaparece de `firing`, y tanto
en el webhook como en MailHog llega un aviso de **resolved**. Eso lo produce el
`send_resolved: true` de los receivers.

Enterarse de que algo volvió a la normalidad es tan importante como enterarse de
que se rompió. Sin eso, alguien se pasa la noche investigando un problema que ya
se arregló solo.

---

## Bloque 4 — Silenciar y comparar con Grafana

**Paso 22 — Un silence.** Imagina que vas a hacer un mantenimiento y sabes que
vas a disparar alertas. Silenciarlas es mejor que borrarlas.

En `http://localhost:9093` → **Silences → New Silence**:

| Campo | Valor |
|---|---|
| Duration | `1h` |
| Matcher | `service` = `order-processor` |
| Creator | tu nombre |
| Comment | `mantenimiento programado` |

Guarda. A partir de ahora las alertas de ese servicio siguen apareciendo en
Prometheus como `firing`, pero Alertmanager no notifica.

Esa diferencia es importante y suele confundir: **Prometheus no deja de detectar
nunca**. El silence vive en Alertmanager y solo afecta al aviso.

Cuando termines, elimina el silence (**Expire**).

**Paso 23 — La misma alerta, al estilo Grafana.** Abre Grafana →
**Alerting → Alert rules**. Verás `TasaErrorAlta (Grafana)` dentro de la carpeta
`OrderFlow`.

No la creó nadie a clics: es el archivo `orderflow-alerts.yml` que copiaste en el
Paso 2, provisionado igual que el dashboard de la Sesión 4.

Ábrela y fíjate en que la condición está partida en tres pasos encadenados:

| Paso | Qué hace |
|---|---|
| **A** | La consulta PromQL. La misma expresión, sin el umbral |
| **B** | *Reduce*: convierte la serie temporal en un solo número |
| **C** | *Threshold*: compara ese número con 10 |

Prometheus lo hace todo en una expresión; Grafana lo separa en pasos que se ven
en pantalla. Ninguno es mejor: Prometheus evalúa pegado al dato y enruta con
Alertmanager, Grafana puede alertar sobre métricas **y logs** desde la misma
herramienta donde está el panel.

**Paso 24.** Ejecuta el validador:

```bash
python scripts/validate_sesion5.py
```

---

## Ejercicios (haz estos tú solo)

### Ejercicio A — Lee el payload

Con una alerta disparada, consulta la API de Alertmanager y averigua **a qué
receptores** se envió, y **cuántas alertas** hay agrupadas en ese momento:

```powershell
Invoke-RestMethod http://localhost:9093/api/v2/alerts
```

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
curl -s http://localhost:9093/api/v2/alerts
```

</details>

Anota el nombre del receptor y el número de alertas activas.

*Pista: cada elemento de la respuesta tiene un campo `receivers` y otro `status`.*

### Ejercicio B — Escribe la cuarta regla

Al final de `prometheus/alerts.yml` hay un bloque `TODO (Sesion 5)`. Escribe ahí
la regla `SinOrdenesProcesadas`:

- **Condición:** no se ha procesado ninguna orden en los últimos 10 minutos.
- **`for`:** `10m`
- **`severity`:** `warning`
- **`service`:** `order-processor`

Después recárgala y compruébala provocando el atasco:

```powershell
Invoke-RestMethod -Method Post http://localhost:9090/-/reload
docker compose stop order-processor
```

Espera y observa `http://localhost:9090/alerts`.

Cuando termines, `docker compose start order-processor`.

*Pista: la tasa de un counter durante una ventana en la que no pasó nada vale
exactamente 0. El nombre de la métrica está en `docs/metricas.md`.*

**Lo interesante viene después.** Al parar el processor vas a disparar **dos**
alertas: `ProcessorCaido` (critical) y la tuya (warning), las dos del mismo
servicio. Mira Alertmanager y explica en dos líneas por qué solo se notifica una.

### Ejercicio C — Diseña un umbral

Elige **una** de las cuatro reglas y responde en tres o cuatro líneas:

- ¿Por qué ese umbral y no uno más alto o más bajo?
- ¿Qué pasaría si el `for` fuera de 10 segundos en vez de los minutos que tiene?
- Si esta alerta sonara tres veces por semana sin que nadie hiciera nada al
  recibirla, ¿qué harías: subir el umbral, alargar el `for`, bajarle la severidad
  o borrarla?

*No hay una respuesta única. Lo que se practica aquí es el criterio: una alerta
que nadie atiende no es una alerta, es ruido, y el ruido hace que también se
ignoren las buenas.*

---

## Si algo falla

| Síntoma | Causa probable | Solución |
|---|---|---|
| `webhook-receiver` no arranca | La imagen no se construyó | `docker compose up -d --build webhook-receiver` |
| `failed to read dockerfile` al construir | Los 3 archivos no están en `services/webhook-receiver/` | Revisa el Paso 1 |
| No aparece `TasaErrorAlta (Grafana)` | Falta el archivo del Paso 2 o Grafana no se recreó | `docker compose up -d --force-recreate grafana` |
| Prometheus no muestra las reglas | No recargaste, o el YAML está mal | `docker compose logs prometheus --tail 30` |
| La alerta nunca pasa de `Inactive` | El nombre de la métrica no existe | Pega la `expr` en la pestaña Graph y mira si devuelve algo |
| Llega al webhook pero no a MailHog | La ruta final tiene matchers | Debe ir sin `matchers`, ver Paso 13 |
| MailHog vacío y sin errores | Alertmanager no recargó | `Invoke-RestMethod -Method Post http://localhost:9093/-/reload` |
| `dial tcp: connection refused` en los logs de Alertmanager | MailHog aún arrancando | Espera 30 s |
| La alerta tarda muchísimo en disparar | Es normal | `rate([5m])` + `for: 2m` suman varios minutos reales |
| Cambié `.env` y no pasa nada | Falta recrear el contenedor | `docker compose up -d order-processor` |

Para cualquier otro problema: `docs/troubleshooting.md`.

---

## Antes de la Sesión 6

1. **Deja `ERROR_RATE_PCT` en `5`.** Si lo dejas en 30, la Sesión 6 te va a dar
   números raros.

2. **Baja el stack:** `docker compose down` (sin `-v`).

3. **Descarga de la plataforma** los cinco archivos de la Sesión 6: los cuatro
   notebooks `.ipynb` y su `requirements.txt`.

4. **Completa el entregable** con la plantilla `scripts/entregable_template.md`.

> En la Sesión 6 dejas de mirar por pantalla. Vas a consultar Prometheus y
> Elasticsearch desde Python, y a construir un informe de salud del pipeline que
> se genera solo.
