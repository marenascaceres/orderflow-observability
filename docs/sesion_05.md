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

Necesitas el stack de la Sesión 4 funcionando, con tu dashboard en
`grafana/dashboards/orderflow-overview.json`.

**Paso 1.** Trae los cambios de esta sesión:

```bash
git pull origin main
```

| Archivo | Qué cambia |
|---|---|
| `docker-compose.yml` | Dos servicios nuevos: `mailhog` y `webhook-receiver` |
| `services/webhook-receiver/` | El microservicio Flask que recibe las alertas |
| `prometheus/alerts.yml` | Pasa de `groups: []` a cuatro reglas (una la escribes tú) |
| `alertmanager/alertmanager.yml` | Enrutamiento, receptores e inhibición reales |
| `grafana/provisioning/alerting/` | La misma alerta, escrita al estilo Grafana |
| `.env.example` | Los puertos de los dos servicios nuevos |

**Paso 2.** Levanta el stack. El `--build` es necesario porque el
`webhook-receiver` es código nuestro y hay que construir su imagen:

```bash
docker compose up -d --build
```

**Paso 3.** Comprueba que ahora son 15:

```bash
docker compose ps --format "table {{.Name}}\t{{.Status}}"
```

En PowerShell funciona igual.

**Paso 4.** Confirma que los dos nuevos responden:

```bash
curl -s http://localhost:5001/health
```

```powershell
Invoke-RestMethod http://localhost:5001/health
```

Debe devolver `{"status":"up"}`.

Y abre `http://localhost:8025` en el navegador: es MailHog, un buzón de correo
vacío. Al final de la sesión tendrá dentro un correo que nadie escribió a mano.

---

## Bloque 1 — Las reglas: qué vigila Prometheus

**Paso 5.** Abre `prometheus/alerts.yml` y léelo entero antes de tocar nada. Son
cuatro reglas y un `TODO`.

Fíjate en la anatomía de `TasaErrorAlta`, porque las cuatro partes hacen cosas
distintas:

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

**Paso 6.** Comprueba que Prometheus sabe a quién avisar. Abre
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

**Paso 7.** Recarga Prometheus sin reiniciarlo:

```bash
curl -X POST http://localhost:9090/-/reload
```

```powershell
Invoke-RestMethod -Method Post http://localhost:9090/-/reload
```

Esto funciona porque el contenedor arranca con `--web.enable-lifecycle`. Sin ese
flag habría que reiniciar Prometheus y perderías el buffer de métricas en curso.

**Paso 8.** Ve a `http://localhost:9090/alerts`.

Verás tus reglas agrupadas, todas en verde y en estado **Inactive**. Todavía no
pasa nada malo. Eso es exactamente lo que debe verse en un sistema sano.

---

## Bloque 2 — Alertmanager: a quién se avisa

**Paso 9.** Abre `alertmanager/alertmanager.yml`.

Prometheus **detecta**. Alertmanager **decide** a quién avisar, cuándo y cuántas
veces. Son dos trabajos distintos y por eso son dos programas distintos.

Tres mecanismos que conviene entender antes de seguir:

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

**Paso 10.** Recarga Alertmanager y comprueba que leyó la configuración nueva:

```bash
curl -X POST http://localhost:9093/-/reload
```

Abre `http://localhost:9093` → pestaña **Status**. Abajo verás la configuración
activa. Confirma que aparecen los dos receivers: `equipo-datos-email` y
`guardia-webhook`.

---

## Bloque 3 — Provocar un incidente de verdad

Hasta aquí todo es teoría con el sistema sano. Vamos a romperlo a propósito.

**Paso 11.** Deja abierta una terminal mirando el webhook en vivo:

```bash
docker compose logs -f webhook-receiver
```

**Paso 12.** En otra terminal, sube la tasa de error simulada. Edita tu `.env`:

```
ERROR_RATE_PCT=30
```

Estaba en 5. Ahora fallará el 30 % de las órdenes, muy por encima del umbral del
10 % de la regla.

**Paso 13.** Aplica el cambio recreando solo el processor:

```bash
docker compose up -d order-processor
```

**Paso 14.** Ve a `http://localhost:9090/alerts` y refresca cada 20 segundos.

Vas a ver tres estados, en este orden:

1. **Inactive** (verde) — la condición todavía no se cumple. La tasa de error se
   calcula sobre 5 minutos, así que tarda en subir.
2. **Pending** (amarillo) — la condición se cumple, pero no lleva los 2 minutos
   del `for`. Prometheus la está cronometrando.
3. **Firing** (rojo) — aguantó los 2 minutos. Ahora sí se envía a Alertmanager.

Ese paso de amarillo a rojo es el `for` haciendo su trabajo. Ten paciencia: entre
que la ventana de 5 minutos se llena y que pasan los 2 minutos del `for`, pueden
irse 4 o 5 minutos reales.

**Paso 15.** En cuanto esté en **Firing**, mira las dos terminales:

- En `http://localhost:9093` la alerta aparece agrupada por `alertname` y `service`.
- En la terminal del webhook aparece el JSON formateado, con severidad, servicio
  y descripción. **Ese es el payload real** que recibiría Slack o PagerDuty.
- En `http://localhost:8025` hay un correo nuevo.

Nadie escribió ese correo. Lo escribió una regla de nueve líneas.

**Paso 16 — Resolver el incidente.** Devuelve el `.env` a su valor sano:

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

**Paso 17 — Un silence.** Imagina que vas a hacer un mantenimiento y sabes que
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

**Paso 18 — La misma alerta, al estilo Grafana.** Abre Grafana →
**Alerting → Alert rules**. Verás `TasaErrorAlta (Grafana)` dentro de la carpeta
`OrderFlow`.

No la creó nadie a clics: llegó en el `git pull` de hoy, en
`grafana/provisioning/alerting/orderflow-alerts.yml`.

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

**Paso 19.** Ejecuta el validador:

```bash
python scripts/validate_sesion5.py
```

---

## Ejercicios (haz estos tú solo)

### Ejercicio A — Lee el payload

Con una alerta disparada, consulta la API de Alertmanager y averigua **a qué
receptores** se envió, y **cuántas alertas** hay agrupadas en ese momento:

```bash
curl -s http://localhost:9093/api/v2/alerts
```

```powershell
Invoke-RestMethod http://localhost:9093/api/v2/alerts
```

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

```bash
curl -X POST http://localhost:9090/-/reload
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
| Prometheus no muestra las reglas | No recargaste, o el YAML está mal | `docker compose logs prometheus --tail 30` |
| La alerta nunca pasa de `Inactive` | El nombre de la métrica no existe | Pega la `expr` en la pestaña Graph y mira si devuelve algo |
| Llega al webhook pero no a MailHog | La ruta final tiene matchers | Debe ir sin `matchers`, ver Paso 9 |
| MailHog vacío y sin errores | Alertmanager no recargó | `curl -X POST http://localhost:9093/-/reload` |
| `dial tcp: connection refused` en los logs de Alertmanager | MailHog aún arrancando | Espera 30 s |
| La alerta tarda muchísimo en disparar | Es normal | `rate([5m])` + `for: 2m` suman varios minutos reales |
| Cambié `.env` y no pasa nada | Falta recrear el contenedor | `docker compose up -d order-processor` |

Para cualquier otro problema: `docs/troubleshooting.md`.

---

## Antes de la Sesión 6

1. **Deja `ERROR_RATE_PCT` en `5`.** Si lo dejas en 30, la Sesión 6 te va a dar
   números raros.

2. **Baja el stack:** `docker compose down` (sin `-v`).

3. **Completa el entregable** con la plantilla `scripts/entregable_template.md`.

> En la Sesión 6 dejas de mirar por pantalla. Vas a consultar Prometheus y
> Elasticsearch desde Python, y a construir un informe de salud del pipeline que
> se genera solo.
