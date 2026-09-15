# Manual de práctica — Sesión 5

## Alertas y notificaciones operativas

**Capítulo 2:** Dashboards, alertas e integración aplicada

> Las diapositivas explican la teoría; los comandos y las consultas salen de aquí.
> Si una consulta de la pantalla no coincide con este documento, manda este documento.
>
> **Una diferencia con las diapositivas:** allí aparece un buzón de correo de prueba
> (MailHog). En la práctica no lo usamos: **las alertas llegan a tu propio Gmail**, igual
> que llegarían en un trabajo real.

---

## Qué vas a construir hoy

Hoy **se llena la tercera y última caja vacía**: Alertmanager.

Hasta ahora, para enterarte de que OrderFlow va mal tenías que estar mirando un
dashboard. Al terminar la sesión **el sistema te avisa solo**, y habrás visto una alerta
recorrer su vida entera:

```
métrica → regla → pending → firing → aviso → resolved
```

Los avisos llegarán por **dos caminos reales**:

| Camino | Quién lo recibe | Para qué |
|---|---|---|
| **Correo a tu Gmail** | Una persona | Que alguien se entere |
| **Webhook** | Un programa | Que un sistema reaccione solo |

El stack crece de 13 a **14 servicios**: el nuevo es el receptor del webhook.

Y ten presente el hilo de toda la sesión desde el principio:

> **El trabajo de un sistema de alertas no es avisar. Es no avisar de más.**
>
> Una alerta que nadie atiende no es una alerta: es ruido. Y el ruido hace que también se
> ignoren las buenas. Casi todo lo que configuras hoy —la espera antes de avisar, la
> agrupación, la inhibición y el silencio— existe para eso.

Al terminar serás capaz de:

- Enviar alertas a un correo real sin dejar la contraseña escrita en el repositorio.
- Explicar qué es un webhook y cómo se usaría en un caso real.
- Configurar Alertmanager: a quién se avisa, cómo se agrupan los avisos y qué se calla.
- Escribir reglas de alerta en Prometheus con condición, espera, etiquetas y textos.
- Provocar un incidente controlado, silenciarlo y seguirlo hasta el aviso de «resuelto».
- Comparar la misma alerta escrita en Prometheus y en Grafana.

---

> **Usa Windows Terminal**, el de las pestañas, no la consola azul clásica. Ésta
> procesa las líneas según le llegan y puede desordenar un bloque pegado de
> varias. Si aparece un `>>` esperando, pulsa `Ctrl+C` y vuelve a pegar.

## Punto de partida

Necesitas tres cosas:

1. **El stack de la Sesión 4 funcionando**, con tu dashboard en
   `grafana/dashboards/orderflow-overview.json`.
2. **Una cuenta de Gmail con la verificación en dos pasos activada.** Si no la tienes,
   actívala antes de empezar desde *Tu cuenta de Google → Seguridad → Verificación en dos
   pasos*. Algunas cuentas de empresa o de centros educativos no permiten el tipo de
   contraseña que vamos a crear; si es tu caso, usa una cuenta personal.
3. **Los seis archivos de la sesión**, descargados de la plataforma en tu carpeta
   `Downloads`:

| Archivo | Para qué programa | Dónde irá |
|---|---|---|
| `app.py` | El receptor del webhook | `services/webhook-receiver/` |
| `Dockerfile` | El receptor del webhook | `services/webhook-receiver/` |
| `requirements.txt` | El receptor del webhook | `services/webhook-receiver/` |
| `alertmanager.yml` | **Alertmanager** | `alertmanager/alertmanager.yml` |
| `alerts.yml` | **Prometheus** | `prometheus/alerts.yml` |
| `orderflow-alerts.yml` | **Grafana** | `grafana/provisioning/alerting/` |

> **Ojo con los dos últimos.** `alerts.yml` y `orderflow-alerts.yml` se parecen en el
> nombre, pero son para programas distintos. Si copias uno en el sitio del otro **no
> aparecerá ningún error**: simplemente no saltará ninguna alerta. Cada vez que copies
> uno, esta guía te recordará para quién es.

**Comprueba también el `uid` fijo** que pusiste a los datasources en la Sesión 4:

```powershell
Select-String "uid:" .\grafana\provisioning\datasources\datasources.yml
```

Tienen que salir `uid: prometheus` y `uid: elasticsearch`.

> **Por qué hoy importa más que nunca.** La alerta de Grafana que instalarás al final dice
> de dónde leer con esa misma palabra: `datasourceUid: prometheus`. Si tu Grafana tuviera
> un identificador generado al azar, la regla no encontraría los datos y **no evaluaría
> nada**, sin dar ningún error. Es la peor forma posible de que falle una alerta.

---

## Dónde se escribe cada cosa

Este manual mezcla varios sitios distintos. Antes de empezar, ten claro cuál es cuál:

| Si el bloque empieza por… | Va en… |
|---|---|
| `docker`, `git`, `Invoke-RestMethod`, `Select-String`, `Copy-Item` | **PowerShell**, siempre desde la carpeta del repositorio |
| `rate(`, `sum(`, `up{` | **El navegador**, en `http://localhost:9090` → pestaña **Graph** |
| Texto con sangría (YAML) | **VS Code**, en el archivo que se indique |
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
`docker-compose.yml` **en la carpeta donde estás parado**.

> **Y si un comando te responde «no se reconoce el término X»**, no está roto tu
> ordenador: ese comando es de otro sistema. En Windows PowerShell se dice así:
>
> | Quiero… | Linux / Mac | Windows PowerShell |
> |---|---|---|
> | Ver solo el final | `tail -20` | `Select-Object -Last 20` |
> | Buscar una palabra | `grep queue` | `Select-String queue` |
> | Contar líneas | `wc -l` | `Measure-Object -Line` |
> | Enviar una petición | `curl -X POST ...` | `Invoke-RestMethod -Method Post ...` |
>
> Ojo con la última: en PowerShell existe un `curl`, pero **no es el mismo programa** y
> los comandos `curl` de internet fallan con errores confusos.

---

## Cómo pegar los bloques de código sin romperlos

Hoy vas a hacer ediciones pequeñas en archivos YAML. **Al copiarlos desde el documento
de Word, los espacios del principio de cada línea se pueden perder.** Y esos espacios no
son decoración: son lo único que indica qué pertenece a qué.

Piensa en una lista de la compra:

```
FRUTAS:
    manzanas
    peras
```

Lo que hace que «manzanas» sea una fruta es que está **escrita más a la derecha** que
FRUTAS. Si la pegas pegada al margen, deja de ser una fruta.

**Después de pegar cualquier bloque, comprueba esto:**

1. Mira la barra azul de abajo a la derecha de VS Code. Debe decir `Spaces: 2`.
2. Compara la primera línea que pegaste con la línea equivalente que ya existía más
   arriba. **Tienen que empezar en la misma columna.**
3. Si tu bloque quedó más a la izquierda: selecciónalo entero y pulsa **`Tab`**.
   `Shift+Tab` lo mueve al revés y `Ctrl+Z` deshace.

**Y una norma para toda la sesión:** los fragmentos que aparecen dentro de una
explicación (con el título «así se lee» o «anatomía») **son para leer, no para pegar**.
Lo que hay que pegar siempre va precedido de «pega esto» y del nombre del archivo.

---

## Las dos piezas de hoy: quién detecta y quién avisa

Antes de tocar nada, conviene tener claro que hoy trabajas con **dos programas
distintos**, y que cada uno tiene su propio archivo:

```
        PROMETHEUS                                    ALERTMANAGER
        (el detector)                                 (la central de avisos)

  mira las métricas cada 15 s                   recibe las alertas
  evalúa las reglas                  ─alerta─>  decide a quién avisar
  decide SI hay un problema                     decide cuándo y cuántas veces
                                                envía el correo y el webhook

  archivo: prometheus/alerts.yml                archivo: alertmanager/alertmanager.yml
```

**Las alertas se crean en Prometheus.** Alertmanager no sabe nada de métricas: solo recibe
lo que Prometheus le entrega y lo reparte.

**Analogía:** Prometheus es el **detector de humo**, que mira y decide si hay fuego.
Alertmanager es la **central de emergencias**: cuando el detector salta, decide a quién
llamar, cómo y cada cuánto insistir.

**El orden de la sesión sigue el de una instalación real:** primero se conecta la central
con los teléfonos (bloques 1 a 3) y se comprueba que suenan. Después se instalan los
detectores (bloque 4). Y al final se provoca un incendio controlado (bloque 5).

---

## Bloque 1 — El correo: una contraseña que no se escribe en el repositorio

Para enviar correo desde Gmail, Alertmanager necesita una contraseña. Y aquí aparece un
problema que vale la pena resolver bien, porque es el mismo que encontrarás en cualquier
sistema real: **¿dónde se guarda una contraseña sin publicarla?**

### Paso 1 — Crear una contraseña de aplicación

**Por qué no sirve tu contraseña de siempre.** Google no permite que un programa entre con
tu contraseña normal, y con razón: con ella, Alertmanager tendría acceso a tu correo
entero, tus documentos y todo lo demás.

En su lugar existen las **contraseñas de aplicación**: una contraseña distinta, larga, que
solo sirve para que un programa envíe correo en tu nombre, y que puedes **revocar cuando
quieras** sin cambiar la tuya.

**Analogía:** es la llave que dejas a quien te cuida el gato. Abre la puerta de casa, pero
no el buzón ni la caja fuerte. Y si la pierde, cambias esa cerradura, no todas.

**Cómo crearla:**

1. Entra en `https://myaccount.google.com/apppasswords` con tu cuenta de Gmail.
2. Si la página dice que la opción no está disponible, te falta la **verificación en dos
   pasos**: actívala en *Seguridad* y vuelve.
3. Escribe un nombre que reconozcas, por ejemplo `OrderFlow Alertmanager`, y pulsa
   **Crear**.
4. Google muestra **16 letras en cuatro grupos**, algo como `abcd efgh ijkl mnop`.

> ⚠️ **Google solo te la enseña una vez.** Déjala visible hasta el Paso 2.
> **Y no la pegues en ningún chat, documento compartido ni comando.** Una contraseña que
> queda escrita en un sitio que no controlas deja de ser secreta.

### Paso 2 — Guardarla en su propio archivo

**El problema:** Alertmanager lee su configuración de `alertmanager/alertmanager.yml`, y
ese archivo **está en git**. Si pusieras ahí la contraseña, la publicarías con el
repositorio. Además, a diferencia de otros programas del stack, **Alertmanager no sabe
leer variables del `.env`** dentro de su configuración.

**La solución:** Alertmanager acepta, en lugar de la contraseña, **la ruta de un archivo
que la contiene**. Ese archivo se queda fuera de git.

```
alertmanager/
├── alertmanager.yml    ← en git. Dice DÓNDE está la contraseña
└── smtp_password       ← fuera de git. CONTIENE la contraseña
```

Crea el archivo vacío y ábrelo en VS Code:

```powershell
New-Item -ItemType File -Force -Path alertmanager\smtp_password | Out-Null; code alertmanager\smtp_password
```

Pega **solo la contraseña**, **sin los espacios** entre grupos (`abcdefghijklmnop`), sin
comillas y sin nada más. Guarda con `Ctrl+S` y cierra la pestaña.

**Por qué en el editor y no con un comando:** todo lo que escribes en PowerShell queda
guardado en su historial, un archivo de texto que cualquiera con acceso a tu equipo puede
leer. **Las contraseñas no se teclean en una terminal.**

> **Llévate esta idea al trabajo:** cuando una herramienta ofrece una opción terminada en
> `_file` (o `__FILE`), casi siempre significa lo mismo: **este valor no debe estar
> escrito en la configuración**. Es la forma habitual de manejar secretos.

### Paso 3 — Comprobar que git no lo verá nunca

`.gitignore` es la lista de archivos que git **no debe mirar nunca**. El repositorio ya
trae una línea que protege ese archivo. Pero una protección que no se comprueba no es una
protección:

```powershell
git check-ignore -v alertmanager/smtp_password
```

**Qué esperamos:** una línea parecida a

```
.gitignore:40:alertmanager/smtp_password    alertmanager/smtp_password
```

Se lee: *«la línea 40 de `.gitignore` hace que git ignore este archivo»*. El número de
línea puede ser otro.

> **Si no aparece nada, el archivo NO está protegido.** Añade tú la línea y vuelve a
> comprobarlo:
>
> ```powershell
> Add-Content .gitignore "`n# Credenciales de Alertmanager: nunca al repositorio`nalertmanager/smtp_password"; git check-ignore -v alertmanager/smtp_password
> ```
>
> No sigas hasta que aparezca la línea: un archivo que se cuela en un commit ya no se
> borra fácilmente del historial.

### Paso 4 — Dejar que Alertmanager vea el archivo

El archivo está en tu disco, pero Alertmanager vive dentro de un contenedor y no lo ve.
Hay que abrirle una ventana: un **volumen**, el mismo concepto que usaste para los
dashboards en la Sesión 4.

> 📄 **Archivo:** `docker-compose.yml` · **servicio:** `alertmanager`

Busca estas líneas:

```yaml
    volumes:
      - ./alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
      - alertmanager_data:/alertmanager
```

Pon el cursor al final de la línea de `alertmanager.yml`, pulsa `Enter` y **pega esto**:

```yaml
      # Sesion 5: la contrasena del correo vive en su propio archivo, fuera
      # de git. Alertmanager no sabe leer variables de entorno, asi que la
      # unica forma de no escribirla en alertmanager.yml es esta.
      - ./alertmanager/smtp_password:/etc/alertmanager/smtp_password:ro
```

Guarda y comprueba:

```powershell
Select-String "smtp_password" .\docker-compose.yml
```

**Qué esperamos:** la línea del volumen (y la del comentario).

**El `:ro` del final** significa *read only*, solo lectura: Alertmanager puede leer la
contraseña, pero no modificarla. Dar el permiso mínimo necesario es la costumbre correcta
con cualquier credencial.

> **Por qué el archivo se creó antes que el volumen:** si le dices a Docker que monte una
> ruta que no existe, **crea una carpeta** con ese nombre. Alertmanager encontraría una
> carpeta donde esperaba un archivo y no podría enviar correo.

Todavía no se aplica nada: lo harás en el Paso 8, junto con el receptor.

---

## Bloque 2 — El webhook: el destino para los programas

### Qué es un webhook

La palabra confunde porque suena a página web, y **no hay ninguna página que abrir**.

> **Un webhook es una dirección a la que un programa envía datos cuando ocurre algo.**

**Analogía: la alarma de una casa.** Cuando salta, pasan dos cosas a la vez:

1. **Te llega un aviso al móvil.** Lo lees tú y decides qué hacer.
2. **Se avisa a la central de alarmas.** Allí no hay nadie mirando un móvil: hay un
   **sistema** que recibe el aviso, lo registra, comprueba cosas y, si hace falta, llama a
   quien corresponda.

**El correo es lo primero. El webhook es lo segundo.**

```
                    ┌──> CORREO ──────> lo lee una PERSONA y decide
Alertmanager ───────┤
                    └──> WEBHOOK ─────> lo recibe un PROGRAMA y actúa
```

| | Correo | Webhook |
|---|---|---|
| Al otro lado hay | Una persona | Un programa |
| Sirve para | Que alguien se entere | Que algo ocurra solo |
| Qué llega | Un texto para leer | Datos ordenados (JSON) |
| Dónde se mira | En la bandeja de entrada | En ningún sitio: el programa **hace algo** con ellos |

### Paso 5 — Copiar el receptor

El receptor de hoy es un programa pequeño en Python que **escucha en una dirección** y,
cuando le llega una alerta, **la imprime** para que puedas verla. Te lo damos hecho: hoy
lo importante es ver qué llega, no escribir Python.

Crea su carpeta y copia dentro los tres archivos:

```powershell
New-Item -ItemType Directory -Force -Path services\webhook-receiver | Out-Null; Copy-Item "$HOME\Downloads\app.py","$HOME\Downloads\Dockerfile","$HOME\Downloads\requirements.txt" services\webhook-receiver\; Get-ChildItem services\webhook-receiver | Select-Object Name, Length
```

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
mkdir -p services/webhook-receiver && cp ~/Downloads/{app.py,Dockerfile,requirements.txt} services/webhook-receiver/ && ls -l services/webhook-receiver
```

</details>

**Qué esperamos:** `app.py`, `Dockerfile` y `requirements.txt`.

**Qué hay en cada archivo:**

| Archivo | Qué contiene |
|---|---|
| `requirements.txt` | Una línea: `flask==3.0.3`. Flask es la librería que permite que un programa de Python atienda peticiones web. |
| `Dockerfile` | Las instrucciones para empaquetar el programa: partir de una imagen con Python 3.11, instalar lo de `requirements.txt`, copiar `app.py`, anunciar el puerto 5001 y arrancarlo. |
| `app.py` | El programa. Unas 80 líneas. |

**Así se lee `app.py`** (para leer, no para pegar):

| Parte | Qué hace |
|---|---|
| `@app.route("/alertas", methods=["POST"])` | Atiende los **envíos** a la dirección `/alertas`. Es donde Alertmanager entrega las alertas. |
| `payload.get("status")`, `payload.get("receiver")` | Lee dos datos generales del aviso: si es de disparo o de resolución, y por qué receptor llegó. |
| `for a in payload.get("alerts", [])` | Un aviso puede traer **varias alertas agrupadas**; las recorre una a una. |
| `labels.get("alertname")`, `labels.get("severity")`… | Lee las **etiquetas** de cada alerta. |
| `ann.get("summary")`, `ann.get("description")` | Lee los **textos** de cada alerta. |
| `print(...)` | Lo muestra en el registro del contenedor. **Aquí es donde un receptor real haría algo útil.** |
| `LOG_PATH` y `f.write(json.dumps(payload))` | Guarda además **el JSON completo** en `/tmp/alertas_recibidas.log`, dentro del contenedor. |
| `return {"ok": True}, 200` | Responde «recibido». Si respondiera un error, Alertmanager reintentaría el envío. |
| `@app.route("/alertas", methods=["GET"])` | Devuelve lo guardado. Lo usa el validador de la sesión. |
| `@app.route("/health")` | Responde `{"status": "up"}` para comprobar que está vivo. |
| `app.run(host="0.0.0.0", port=5001)` | `0.0.0.0` significa «acepta conexiones desde otros contenedores», no solo desde dentro de él. |

> **Por qué el receptor es local y no un servicio de internet.** Existen webs que reciben
> webhooks y los muestran. El problema en un aula es que dependen de la conexión, del
> proxy de la red y de los certificados: basta con que un filtro de red intercepte el
> tráfico para que el navegador muestre «La conexión no es privada» y la clase se detenga.
> Un receptor local no depende de nada de eso, y además **los datos de las alertas no
> salen de tu equipo**.
>
> Y si alguna vez ves ese aviso de certificado en el trabajo: **no pulses «continuar de
> todos modos»**. Significa que el servidor no ha podido demostrar que es quien dice ser.

### Cómo se llevaría esto a un caso real

El receptor de hoy **imprime** la alerta y poco más. Parece poca cosa, pero es la pieza
sobre la que se construyen casi todas las automatizaciones de un equipo de operaciones.

**Lo que has copiado, en una frase:** *un programa tuyo que recibe las alertas y decide qué
hacer con ellas.* Alertmanager no sabe ni le importa qué hay al otro lado: envía los datos
a una dirección y se desentiende.

**Por qué importa.** Avisar a una persona resuelve muchos casos, pero no todos:

| Lo que quieres | ¿Basta con avisar a alguien? |
|---|---|
| Que el equipo se entere | Sí |
| **Que quede registro de cada incidencia sin escribirlo a mano** | No |
| **Que solo se avise a quien esté de guardia hoy** | No |
| **Que se intente arreglar antes de molestar a nadie** | No |
| **Saber a fin de mes qué falló más veces** | No |

Todo lo que dice «No» necesita código. Y ese código vive exactamente en un receptor como
éste. Tres usos reales:

**1. Dejar constancia automática.** Salta una alerta de madrugada, alguien la arregla y
se vuelve a dormir. Al día siguiente nadie lo recuerda. Un receptor puede **abrir una
incidencia** en el sistema del equipo con los datos ya rellenos (servicio, gravedad,
hora) y **cerrarla** cuando llegue el aviso de «resuelto».

**2. Avisar solo a quien corresponde.** Si hay turnos de guardia, avisar a todos hace que
nadie se sienta responsable. Un receptor puede **consultar el calendario de guardias**
(una hoja de cálculo, una tabla, un sistema interno), mirar quién está hoy y reenviar
solo a esa persona. Alertmanager sabe repartir por etiquetas fijas, pero no sabe
consultar vuestro calendario: esa lógica es vuestra.

**3. Intentar resolverlo antes de avisar.** Hay averías que casi siempre se arreglan con
la misma acción. Un receptor puede intentarla, esperar, comprobar y **avisar solo si no
se resolvió**, dejando constancia en ambos casos.

**Cómo se despliega una solución así**, de menos a más infraestructura:

| Forma | Cómo es | Cuándo encaja |
|---|---|---|
| **Un flujo en una plataforma de automatización** | Se crea un flujo que empieza con «cuando llegue una solicitud web». La plataforma da una dirección, y esa dirección se pone en la configuración de alertas. Desde el flujo se crea la incidencia, se escribe en una hoja o se envía un mensaje. **No hay que instalar nada.** | Cuando no se tienen permisos sobre servidores |
| **Una función en la nube** | Se sube solo el código, sin mantener ningún servidor. Solo consume cuando se ejecuta. | Cuando las alertas son pocas y espaciadas |
| **Un servicio propio** | Un programa pequeño en un contenedor o en una máquina existente, **como el de hoy**. | Cuando el receptor tiene que hablar con sistemas internos |

**Las tres reciben exactamente el mismo JSON.** Por eso lo que ves hoy sirve para las
tres: cambia dónde vive el código, no lo que llega.

### Paso 6 — Añadir el receptor al stack

> 📄 **Archivo:** `docker-compose.yml` · **al final del archivo**

Baja hasta la última línea del archivo (la del último servicio) y **pega esto** debajo,
con una línea en blanco de separación:

```yaml
  # ============================================================
  # DESTINO DE NOTIFICACION (anadido en la Sesion 5)
  # ============================================================
  # Programa que recibe el aviso de Alertmanager y lo imprime. Es local
  # a proposito: no depende de internet, del proxy ni de certificados
  # ajenos, y los datos de las alertas no salen de la maquina.
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

La primera línea, `webhook-receiver:`, debe quedar **en la misma columna** que los demás
servicios (por ejemplo, `kibana:`).

**Lo nuevo aquí es `build:`**, y es la primera vez que aparece en el curso:

| | `image:` | `build:` |
|---|---|---|
| Qué significa | Usa un programa que **ya existe empaquetado** | **Empaqueta tú** el programa con su `Dockerfile` |
| Quién lo usa | Los 13 servicios anteriores | El receptor |
| Analogía | Un electrodoméstico que llega montado | Un mueble que llega en piezas con sus instrucciones, y Docker lo monta |

`context: ./services/webhook-receiver` dice **dónde están las piezas**, y `dockerfile:`
cuál es el archivo de instrucciones.

### Paso 7 — Declarar el puerto en tu `.env`

> 📄 **Archivo:** `.env` (no el `.env.example`) · **al final**

```
# --- Destino de notificacion (anadido en la Sesion 5) ---
# webhook-receiver: programa que imprime el JSON de las alertas.
WEBHOOK_PORT=5001
```

Guarda y comprueba:

```powershell
Select-String "WEBHOOK_PORT" .env
```

### Paso 8 — Construir y levantar

```powershell
docker compose up -d --build
```

**Qué hace `--build`:** además de levantar, **construye** los servicios que tienen
`build:`. La primera vez tarda cerca de un minuto: Docker descarga Python, instala Flask y
empaqueta el programa.

**Qué esperamos ver:**

- `orderflow-webhook-receiver` → **`Started`**.
- `orderflow-alertmanager` → **`Recreated`**.

**¿Por qué se recrea Alertmanager si no lo has tocado?** Sí lo has tocado: le añadiste un
volumen en el Paso 4. **Los volúmenes se asignan cuando el contenedor nace**, así que
Docker lo tiene que crear de nuevo. Un `docker compose restart` no habría servido: habría
reiniciado el mismo contenedor, sin la ventana al archivo de la contraseña.

Cuenta los servicios:

```powershell
docker compose ps --format "{{.Name}}" | Measure-Object -Line
```

**Qué esperamos:** `14` en la columna **Lines**.

> Si el mensaje de `up` dice algo como `15/15`, no te confundas: Docker cuenta **todo lo
> que crea**, y eso incluye la red. El dato que vale es el recuento de contenedores.

Y comprueba que el receptor responde:

```powershell
Invoke-RestMethod http://localhost:5001/health
```

**Qué esperamos:** `status` → `up`.

> **Si abres `http://localhost:5001` en el navegador verás un error 404.** Es lo normal:
> el programa solo atiende en `/alertas` y `/health`. No es una página para mirar, es un
> programa esperando que otro le hable.

---

## Bloque 3 — Alertmanager: a quién se avisa

Ahora se conecta la central de avisos con los dos destinos.

### Paso 9 — Instalar la configuración de Alertmanager

> 📄 Archivo del LMS: **`alertmanager.yml`** → es para **Alertmanager**.

El archivo actual solo tiene un receptor vacío, puesto en la Sesión 1 para que
Alertmanager arrancara sin quejarse. Lo sustituyes por el de la plataforma y lo abres:

```powershell
Copy-Item "$HOME\Downloads\alertmanager.yml" .\alertmanager\alertmanager.yml -Force; code .\alertmanager\alertmanager.yml
```

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
cp ~/Downloads/alertmanager.yml alertmanager/alertmanager.yml && code alertmanager/alertmanager.yml
```

</details>

**Pon tu dirección de correo.** En VS Code pulsa `Ctrl+H` (buscar y reemplazar):

- **Buscar:** `TU_CORREO@gmail.com`
- **Reemplazar:** tu dirección de Gmail
- Pulsa **Reemplazar todo**. VS Code debe indicar **3 reemplazos**.

Guarda con `Ctrl+S`.

**Las tres líneas que cambian son:** el remitente (`smtp_from`), el usuario con el que se
entra en Gmail (`smtp_auth_username`) y el destinatario (`to`). Con Gmail, remitente y
usuario tienen que ser tu propia dirección: Google no deja enviar en nombre de otra. El
destinatario también es tu dirección, porque te envías los avisos a ti mismo.

### Qué hace cada parte del archivo

Léelo con el archivo abierto al lado. Tiene cinco partes.

#### 1. `global` — cómo se envía el correo

| Línea | Qué significa |
|---|---|
| `resolve_timeout: 5m` | Si Alertmanager deja de recibir noticias de una alerta durante 5 minutos, la da por resuelta. |
| `smtp_smarthost: 'smtp.gmail.com:587'` | El servidor de salida de Google. El `587` es el puerto estándar de envío con cifrado. |
| `smtp_from` / `smtp_auth_username` | Quién envía y con qué usuario se identifica. |
| `smtp_auth_password_file: '/etc/alertmanager/smtp_password'` | **Dónde está la contraseña**, no la contraseña. Es la ruta **dentro del contenedor**: la que abriste con el volumen del Paso 4. |
| `smtp_require_tls: true` | Exige cifrar la conexión con Google. |

#### 2. `route` — el árbol que decide a quién avisar

Se recorre **de arriba abajo**, como un árbol de decisiones:

```
                       llega una alerta
                             │
               ¿tiene severity="critical"?
                    │                 │
                   SÍ                 NO
                    │                 │
          guardia-webhook             │
          (y continue: true)          │
                    │                 │
                    └────────┬────────┘
                             │
                    equipo-datos-email
```

| Tipo de alerta | Llega a |
|---|---|
| **critical** | Webhook **y** correo |
| **warning** | Solo correo |

**Por qué así:** lo crítico debe dejar rastro en los sistemas (un registro, una
incidencia) además de avisar a una persona. Un aviso menor basta con que alguien lo lea.

**Las dos líneas que hacen que funcione:**

- **`continue: true`** en la ruta del webhook. Por defecto, **en cuanto una alerta encaja
  en una ruta, deja de bajar**. Sin esta línea, una alerta crítica llegaría al webhook y a
  ningún sitio más: nunca al correo.
- **La última ruta no tiene `matchers`** (condiciones), así que recoge **todo** lo que
  llegue hasta ella.

> **El fallo silencioso clásico de Alertmanager:** si esa última ruta tuviera la condición
> `severity="warning"`, las alertas críticas no encajarían en ella y **jamás llegarían al
> correo**. La configuración sería válida, Alertmanager arrancaría sin quejarse, y la
> mitad de los avisos desaparecería sin que nadie lo notara.

#### 3. Los tiempos — la agrupación

| Opción | Valor | Qué hace | Analogía |
|---|---|---|---|
| `group_by` | `['alertname', 'service']` | Junta en **un solo aviso** las alertas con el mismo nombre y servicio | Un correo con cuarenta pedidos fallidos, no cuarenta correos |
| `group_wait` | `30s` | Espera antes del **primer** aviso de un grupo, por si llegan alertas hermanas | Esperar un momento antes de llamar, por si hay más que contar |
| `group_interval` | `5m` | Cada cuánto se revisa un grupo ya avisado para informar de **novedades** (incluido el «resuelto») | No volver a llamar por cada detalle |
| `repeat_interval` | `3h` | Cada cuánto se **recuerda** algo que sigue roto | El recordatorio si nadie lo ha arreglado |

La ruta crítica los acorta: **`group_wait: 10s`** y **`repeat_interval: 1h`**. Lo urgente
se avisa antes y se recuerda más a menudo.

#### 4. `receivers` — los destinos

| Receptor | Canal | Para quién |
|---|---|---|
| `equipo-datos-email` | `email_configs` → tu correo | Una persona |
| `guardia-webhook` | `webhook_configs` → `http://webhook-receiver:5001/alertas` | Un programa |

Dos detalles:

- **`send_resolved: true`** en los dos: también se avisa cuando la alerta **se resuelve**.
  Saber que algo volvió a la normalidad es tan útil como saber que se rompió: evita que
  alguien pase la noche investigando un problema que ya se arregló solo.
- **La dirección del webhook usa `webhook-receiver`, no `localhost`.** Dentro de la red de
  Docker, cada servicio se llama por su nombre. Alertmanager y el receptor son vecinos en
  esa red. Tú, desde el navegador, estás fuera de ella y usarías `localhost:5001`. **El
  mismo sitio tiene dos nombres según desde dónde preguntes.**

> **¿Y las herramientas de mensajería de equipo, como Slack o Microsoft Teams?** No las
> usamos en clase, pero funcionan con la misma idea. Alertmanager tiene integraciones
> propias para ellas (`slack_configs`, `msteams_configs`): en la herramienta se crea una
> **dirección de entrada** para un canal, y esa dirección se pone en un receptor, igual que
> hoy pones la del webhook. El árbol de rutas, la agrupación y la inhibición funcionan
> exactamente igual. Lo que cambia es el aspecto del mensaje, no la lógica.
>
> **Cómo se elige el canal:** por lo que quieres que ocurra cuando llegue. ¿Que alguien lo
> lea mañana? Correo. ¿Que el equipo lo vea hoy? Un canal de mensajería. ¿Que un sistema
> reaccione? Un webhook. **El error más común es enviarlo todo al mismo sitio:** en dos
> semanas nadie mira ese canal.

#### 5. `inhibit_rules` — callar lo que sobra

```yaml
inhibit_rules:
  - source_matchers:
      - severity="critical"
    target_matchers:
      - severity="warning"
    equal: ['service']
```

**Se lee:** *«mientras haya una alerta crítica de un servicio, calla los avisos de gravedad
warning del mismo servicio»*.

**El ejemplo:** si el processor se cae, también se dispararán avisos que son
**consecuencia** de esa caída. Recibirlos en ese momento solo añade ruido.

**`equal: ['service']` es imprescindible:** sin esa línea, una alerta crítica de cualquier
servicio callaría los avisos de **todos** los demás, aunque no tuvieran nada que ver.

### Paso 10 — Validar antes de aplicar

Primero, comprueba que la contraseña **no** está escrita en el archivo:

```powershell
"con _file (debe ser 1): $((Select-String 'smtp_auth_password_file' .\alertmanager\alertmanager.yml).Count)"; "escrita (debe ser 0): $((Select-String 'smtp_auth_password:' .\alertmanager\alertmanager.yml).Count)"; "TU_CORREO (debe ser 0): $((Select-String 'TU_CORREO' .\alertmanager\alertmanager.yml).Count)"
```

**La segunda línea es la importante:** si `smtp_auth_password:` (sin `_file`) apareciera,
significaría que alguien escribió la contraseña en un archivo que va a git.

Después, pide a la herramienta oficial de Alertmanager que lea el archivo y diga si lo
entiende:

```powershell
docker run --rm --entrypoint amtool -v "${PWD}/alertmanager:/cfg" prom/alertmanager:v0.27.0 check-config /cfg/alertmanager.yml
```

**Qué esperamos:** `SUCCESS` y un resumen que incluya **`2 receivers`** y
**`1 inhibit rules`**.

**Qué hace ese comando, por partes:**

| Parte | Qué significa |
|---|---|
| `docker run --rm` | Arranca un contenedor de usar y tirar, que se borra al terminar |
| `--entrypoint amtool` | **Arranca la herramienta `amtool`**, no el servicio |
| `-v "${PWD}/alertmanager:/cfg"` | Le presta tu carpeta `alertmanager` como `/cfg` |
| `check-config /cfg/alertmanager.yml` | Le pide que revise el archivo |

> **Por qué hace falta `--entrypoint`.** Cada imagen de Docker trae **un programa
> predeterminado**. La de Alertmanager arranca siempre `alertmanager`, y sin
> `--entrypoint` tomaría `amtool` como si fuera una opción suya:
> `alertmanager: error: unexpected amtool`. Es la causa de muchos comandos copiados de
> internet que fallan con errores confusos.

### Paso 11 — Que Alertmanager cargue la configuración

```powershell
Invoke-RestMethod -Method Post http://localhost:9093/-/reload
```

**Qué esperamos:** que no devuelva nada. En este caso, vacío significa éxito.

Alertmanager **relee su configuración sin pararse**. Aquí no hace falta recrear el
contenedor, porque no cambiaste `docker-compose.yml`: solo un archivo que el programa lee.

Comprueba que la cargó: abre `http://localhost:9093/#/status`, baja hasta **Config** y
busca en `receivers` los dos nombres: `equipo-datos-email` y `guardia-webhook`. Lo que
ves ahí es la configuración que está usando **ahora mismo**, no la del archivo.

### Paso 12 — Probar el canal antes de construir nada encima

Vas a dedicar el resto de la sesión a escribir reglas. **Si el correo no funcionara, no
lo descubrirías hasta el final**, y entonces no sabrías si el fallo está en la regla, en
el árbol de rutas o en el envío.

> **Se comprueba que suena el timbre antes de esperar visitas.**

Alertmanager tiene una puerta para recibir alertas a mano. Le vas a entregar una
inventada, como si viniera de Prometheus:

```powershell
Invoke-RestMethod -Method Post "http://localhost:9093/api/v2/alerts" -ContentType "application/json" -Body '[{"labels":{"alertname":"PruebaDeNotificacion","severity":"critical","service":"order-processor","region":"lima"},"annotations":{"summary":"El procesador de pedidos no responde","description":"Alerta de prueba para comprobar que el aviso llega al correo y al receptor."}}]'
```

**Qué le estás entregando:**

| Grupo | Datos |
|---|---|
| `labels` (etiquetas) | `alertname`, `severity`, `service`, `region` |
| `annotations` (textos) | `summary`, `description` |

Como es `critical`, el árbol la enviará **a los dos destinos**. **Espera unos 40
segundos** (los `group_wait` de 10 y 30 segundos) y mira qué llegó al receptor:

```powershell
docker compose logs webhook-receiver --tail 30
```

**Qué esperamos:**

```
===== ALERTA RECIBIDA @ ... =====
  status global : firing
  receiver      : guardia-webhook
----------------------------------------------------
  estado    : firing
  alerta    : PruebaDeNotificacion
  severidad : critical
  servicio  : order-processor
  resumen   : El procesador de pedidos no responde
  detalle   : Alerta de prueba para comprobar que el aviso llega al correo y al receptor.
172.18.0.x - - [...] "POST /alertas HTTP/1.1" 200 -
```

Y **mira tu Gmail**: debe haber un correo con `[FIRING:1] PruebaDeNotificacion` en el
asunto. **Revisa también la carpeta de spam**: un correo automático que te envías a ti
mismo es candidato claro.

> **Si el correo no llega en dos minutos:** mira el registro de Alertmanager con
> `docker compose logs alertmanager --tail 20`. Un `535 Username and Password not
> accepted` significa que la contraseña de aplicación es incorrecta o tiene espacios.

### Lo que acaba de llegar: el contrato

Compara lo que escribiste con lo que imprimió el receptor:

| Lo que escribiste | Lo que llegó |
|---|---|
| `"alertname": "PruebaDeNotificacion"` | `alerta : PruebaDeNotificacion` |
| `"severity": "critical"` | `severidad : critical` |
| `"service": "order-processor"` | `servicio : order-processor` |
| `"summary": "El procesador..."` | `resumen : El procesador...` |

**Llegó intacto.** Y es lo más importante que hay que entender de un webhook:

> **Lo que escribes en una alerta es exactamente lo que llega al otro lado.** Esa estructura
> no cambia: es la misma que llegaría a cualquier receptor, esté donde esté.

Los datos llegan en **dos grupos que no son intercambiables**:

| Grupo | Qué contiene | Para qué sirve |
|---|---|---|
| **`labels`** | Datos cortos: qué alerta, qué gravedad, qué servicio | **Decidir**: a quién se avisa, qué se agrupa, qué se silencia |
| **`annotations`** | Texto para personas | **Leer**: lo que aparece en el aviso |

> **La regla que conviene memorizar:** las etiquetas son para la máquina; las anotaciones,
> para la persona. **Por las etiquetas se puede filtrar; por las anotaciones, no.** Si
> quieres que las alertas de Lima vayan a un sitio distinto, `region` tiene que ser una
> etiqueta. Si la escribes solo en la descripción, ya no puedes repartir por ella.

Hay datos que **no escribiste tú** y los añade Alertmanager:

| Dato | Qué es | Para qué lo usaría un receptor real |
|---|---|---|
| `status` | `firing` al empezar, `resolved` al terminar | Abrir una incidencia o cerrarla |
| `receiver` | Por qué receptor llegó | Tratar distinto cada camino |
| `200` al final de la línea | La respuesta del receptor: «recibido» | Si fuera un error, Alertmanager reintentaría |

**El receptor guarda también el JSON completo**, con más datos todavía:

```powershell
docker compose exec webhook-receiver cat /tmp/alertas_recibidas.log
```

Busca en él estos campos:

| Campo | Qué es |
|---|---|
| `startsAt` | Cuándo empezó el problema |
| `endsAt` | Cuándo terminó, o una fecha de caducidad si sigue activo |
| `fingerprint` | Un identificador único de **esa** alerta. Permite saber que un «resuelto» corresponde a un «disparo» anterior y cerrar la incidencia correcta |
| `groupKey` | Con qué criterio se agrupó |

> **En unos 5 minutos llegará un segundo aviso**, con `resolved`, por los dos caminos. La
> alerta inventada no se renueva, y Alertmanager la da por resuelta cuando pasa el
> `resolve_timeout` de 5 minutos. No hace falta esperarlo: puedes seguir.

**Los dos canales funcionan.** Ahora toca decidir **qué merece un aviso**.

---

## Bloque 4 — Prometheus: qué se vigila

### Paso 13 — Instalar las reglas

> 📄 Archivo del LMS: **`alerts.yml`** → es para **Prometheus**, no para Grafana.

Tu `prometheus/alerts.yml` contiene hoy esto:

```yaml
groups: []
```

Una lista de reglas **vacía**. Por eso Alertmanager lleva cuatro sesiones sin recibir
nada. Aquí sí se sustituye el archivo entero, porque no hay nada que conservar:

```powershell
Copy-Item "$HOME\Downloads\alerts.yml" .\prometheus\alerts.yml -Force
```

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
cp ~/Downloads/alerts.yml prometheus/alerts.yml
```

</details>

Y valida con la herramienta oficial de Prometheus, con el mismo gesto que usaste con
Alertmanager:

```powershell
docker run --rm --entrypoint promtool -v "${PWD}/prometheus:/cfg" prom/prometheus:v2.51.0 check rules /cfg/alerts.yml
```

**Qué esperamos:** `SUCCESS: 4 rules found`.

> **Por qué validar siempre antes de aplicar.** Si el archivo tuviera un error y
> recargaras Prometheus sin comprobarlo, Prometheus **rechazaría el archivo entero y
> seguiría funcionando con la lista vacía, sin avisar de que no tiene alertas**.
> `promtool` te dice la línea y el motivo antes de que eso ocurra.

### Paso 14 — Entender el archivo

Abre `prometheus/alerts.yml` en VS Code y léelo con esta explicación al lado.

#### La estructura

**Así se lee** (para leer, no para pegar):

```yaml
groups:
  - name: orderflow_disponibilidad
    rules:
      - alert: ...
      - alert: ...
  - name: orderflow_procesamiento
    rules:
      - alert: ...
      - alert: ...
```

| Nivel | Qué es | Analogía |
|---|---|---|
| `groups` | La lista de todos los grupos | El libro |
| `- name:` | Un grupo de reglas relacionadas | Un capítulo |
| `- alert:` | Una regla concreta | Una página |

Hay dos grupos que responden a dos preguntas: **¿están vivos los servicios?** y **¿están
trabajando bien?**

#### Las cinco piezas de una regla

**Anatomía** (para leer, no para pegar):

```yaml
- alert: NombreDeLaAlerta     # 1. cómo se llama
  expr: condición             # 2. cuándo hay problema
  for: tiempo                 # 3. cuánto aguantar antes de avisar
  labels:                     # 4. datos para decidir a quién avisar
    severity: ...
  annotations:                # 5. texto para quien lo lea
    summary: ...
```

| Pieza | Para qué sirve | Analogía |
|---|---|---|
| **`alert`** | El nombre que verás en el correo y en el receptor | El título del aviso |
| **`expr`** | La condición. Mientras devuelva resultado, hay problema | El sensor |
| **`for`** | Cuánto tiene que durar antes de avisar | La paciencia |
| **`labels`** | Etiquetas para repartir, agrupar y silenciar | Los datos para la máquina |
| **`annotations`** | El texto del aviso | Lo que lee la persona |

#### La vida de una alerta

```
condición falsa       condición cierta          sigue cierta           deja de ser cierta
   INACTIVE     ──>       PENDING         ──>      FIRING         ──>      RESOLVED
  (todo bien)       (la ve, pero espera        (se entrega a           (se avisa de que
                     el tiempo del for)          Alertmanager)            se arregló)
```

**El `pending` es lo que evita los falsos avisos.** Si la condición deja de cumplirse antes
de agotar el `for`, la alerta vuelve a `inactive` **sin haber molestado a nadie**.

**Analogía:** un detector de humo que no suena por el vapor de la ducha, pero sí si el humo
sigue ahí.

#### Grupo 1 — Disponibilidad

**`ProcessorCaido`**: *«el processor no contesta a Prometheus»*.

| Parte | Explicación |
|---|---|
| `up{job="order-processor"} == 0` | `up` es una métrica que **Prometheus crea por su cuenta** para cada programa que vigila: vale `1` si pudo leerlo y `0` si no. El filtro `{job="order-processor"}` se queda solo con la del processor. |
| `for: 1m` | Una lectura fallida suelta puede ser un parpadeo de red. Un minuto entero sin contestar ya es un problema. |
| `severity: critical` | Si el processor cae, **no se atiende ni un pedido**. |
| `{{ $labels.instance }}` en la descripción | Se rellena solo con la instancia concreta que falló. |

**`GeneratorCaido`**: la misma idea para el generator, pero **`warning`**. Si cae, dejan de
entrar pedidos nuevos, pero los que ya están en la cola se siguen procesando.

> **Decidir qué es crítico y qué es un aviso es la parte más importante de diseñar alertas,
> y no es técnica.** Es una pregunta de negocio: ¿qué duele más y qué justifica despertar a
> alguien?

#### Grupo 2 — Procesamiento

**`TasaErrorAlta`**: *«más del 10 % de los pedidos está fallando»*.

**Así se lee la expresión**, de dentro hacia fuera:

```
              pedidos fallidos por segundo
100  ×  ──────────────────────────────────────────   >  10
         procesados por segundo + fallidos por segundo
```

| Parte | Explicación |
|---|---|
| `rate(...[5m])` | Convierte un contador que solo sube en una velocidad: cuántos por segundo en los últimos 5 minutos. |
| `clamp_min(..., 0.001)` | Pone un suelo al denominador para no dividir entre cero. |
| `for: 2m` | Unos pocos fallos seguidos pueden disparar el porcentaje un instante. Dos minutos por encima ya es un patrón. |
| `{{ printf "%.1f" $value }}` | Escribe en la descripción **el valor real** con un decimal: `25.3` en vez de `25.318271`. |

> **Es la misma consulta del panel «Tasa de error %» de la Sesión 4.** Es deliberado: si el
> gráfico midiera de una forma y la alerta de otra, llegaría el día en que el panel está
> verde y el correo dice que todo arde. El panel se pone amarillo al 5 % y rojo al 15 %; la
> alerta avisa al pasar del 10 %, en plena zona amarilla.

**`LatenciaAltaP95`**: *«el 5 % más lento de los pedidos tarda más de 1 segundo»*.

| Parte | Explicación |
|---|---|
| `histogram_quantile(0.95, ...)` | Calcula el P95: el tiempo por debajo del cual está el 95 % de los pedidos. |
| `sum by (le)` y `_bucket` | Igual que en Grafana: sin ellos la expresión devuelve `NaN` y la alerta no dispara nunca. |
| `for: 5m` | La latencia sube y baja con la carga; cinco minutos seguidos lentos ya indican algo. |
| `warning` | El sistema sigue funcionando, solo más lento. |

**Por qué P95 y no la media:** si 99 pedidos tardan una décima y uno tarda treinta
segundos, la media sale bien y hay un cliente esperando medio minuto. El P95 no lo esconde.

#### Las cuatro de un vistazo

| Alerta | Pregunta | Paciencia | Gravedad |
|---|---|---|---|
| `ProcessorCaido` | ¿Está vivo el processor? | 1 min | critical |
| `GeneratorCaido` | ¿Está vivo el generator? | 1 min | warning |
| `TasaErrorAlta` | ¿Falla más del 10 %? | 2 min | critical |
| `LatenciaAltaP95` | ¿Espera alguien más de 1 s? | 5 min | warning |

**Fíjate en el patrón:** lo que es blanco o negro (un servicio caído) se avisa rápido; lo
que fluctúa por naturaleza (errores, latencia) necesita más paciencia para no avisar en
falso.

#### Dos detalles de escritura

- **`>-`** delante de un texto significa *«esto ocupa varias líneas en el archivo:
  júntalas en una sola»*. Permite escribir descripciones legibles sin que el aviso llegue
  partido.
- **El bloque `TODO` del final no es una regla, es un comentario.** Por eso `promtool`
  cuenta cuatro. Es el **Ejercicio B**.

### Paso 15 — Comprobar que Prometheus sabe a quién entregar

Abre `prometheus/prometheus.yml` y localiza estos dos bloques, que están ahí desde la
Sesión 1:

```yaml
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

rule_files:
  - /etc/prometheus/alerts.yml
```

| Bloque | Qué dice |
|---|---|
| `alerting` | A qué Alertmanager entregar las alertas. Sin él, Prometheus detectaría el problema y no se lo contaría a nadie. |
| `rule_files` | Qué archivo de reglas leer. Es la ruta **dentro del contenedor** de tu `prometheus/alerts.yml`. |

No hay que cambiar nada.

### Paso 16 — Cargar las reglas y verlas

```powershell
Invoke-RestMethod -Method Post http://localhost:9090/-/reload
```

Prometheus **relee sus reglas sin pararse**: no pierde datos ni deja de vigilar mientras
recarga. Funciona porque su contenedor arranca con la opción `--web.enable-lifecycle`; sin
ella habría que reiniciarlo.

Abre `http://localhost:9090/alerts`.

**Qué esperamos:** las cuatro reglas en sus dos grupos, **todas en verde** con el estado
**Inactive**. Pulsa sobre cualquiera para ver su expresión, su `for`, sus etiquetas y sus
textos.

| Color | Estado | Qué significa |
|---|---|---|
| 🟢 Verde | `inactive` | La condición no se cumple. Todo bien |
| 🟡 Amarillo | `pending` | Se cumple, pero todavía está esperando el `for` |
| 🔴 Rojo | `firing` | Se cumplió el tiempo entero. **Ya se entregó a Alertmanager** |

**Todo en verde es exactamente lo que debe verse en un sistema sano.**

> **Si no aparece ninguna regla**, mira `docker compose logs prometheus --tail 30`.
> Probablemente no recargaste o el archivo no pasó `promtool`.

---

## Bloque 5 — Provocar un incidente de verdad

Hasta aquí, todo con el sistema sano. Ahora lo vas a romper a propósito para ver una
alerta nacer, avisar, silenciarse y resolverse.

### Paso 17 — Preparar una ventana para mirar

Abre **una segunda pestaña** en Windows Terminal (`Ctrl+Shift+T`) y deja esto corriendo:

```powershell
cd C:\ruta\donde\clonaste\orderflow-observability; docker compose logs -f webhook-receiver
```

**`-f`** (*follow*, seguir) deja la pestaña **escuchando**: cada aviso nuevo aparece en
cuanto llega. Es como se trabaja durante un incidente: en una pestaña provocas o arreglas,
en la otra ves llegar los avisos. Para dejar de escuchar, `Ctrl+C`.

### Paso 18 — Subir la tasa de errores

Vuelve a la **primera pestaña**.

> 📄 **Archivo:** `.env`

Busca `ERROR_RATE_PCT=5` y cámbialo por:

```
ERROR_RATE_PCT=30
```

Guarda. Con 30, fallará casi uno de cada tres pedidos: **tres veces el umbral del 10 %**.

Aplica el cambio y compruébalo **dentro del contenedor**:

```powershell
docker compose up -d order-processor; docker compose exec order-processor printenv ERROR_RATE_PCT
```

**Qué esperamos:** `Recreated` o `Started` en el processor y, debajo, **`30`**.

| Comando | Por qué |
|---|---|
| `up -d`, no `restart` | Las variables del `.env` se entregan al contenedor **cuando nace**. `restart` reiniciaría el mismo contenedor con el valor antiguo. |
| `printenv` | Pregunta al **propio programa** qué valor tiene. Es la diferencia entre «lo he escrito» y «el programa lo está usando». Si aquí saliera `5`, esperarías media hora a una alerta que nunca llegaría. |

> Verás también `postgres` y `redis` como `Healthy`: el processor depende de ellos, y
> Docker comprueba que estén sanos antes de encenderlo. No los reinicia.

### Paso 19 — Ver la alerta pasar por los tres colores

Abre `http://localhost:9090/alerts` y refresca cada 20 o 30 segundos mirando
**`TasaErrorAlta`**.

**Al principio seguirá en verde, y es normal:**

```
la regla mira los últimos 5 minutos     +     exige 2 minutos seguidos (for)
               ↓                                          ↓
el porcentaje sube poco a poco,               aunque ya pase del 10 %,
porque la ventana aún tiene datos             espera antes de entregarla
de cuando todo iba bien
```

**Cuenta con 4 o 5 minutos** hasta el rojo.

1. 🟢 **Verde:** el porcentaje todavía no pasa del 10 %.
2. 🟡 **Amarillo (`pending`):** ya pasa, y Prometheus está **cronometrando** los 2 minutos.
   Despliega la alerta: **Active Since** dice desde cuándo, y **Value**, el porcentaje
   actual. En este momento **no ha avisado a nadie**.
3. 🔴 **Rojo (`firing`):** aguantó los 2 minutos y se entregó a Alertmanager.

> **El amarillo es lo que hace que confíes en el rojo.** Sin él, cualquier racha de diez
> segundos te enviaría un correo; en una semana tendrías cien avisos falsos y dejarías de
> leerlos.

### Paso 20 — Ver llegar los avisos

**En la pestaña del webhook**, a los pocos segundos del rojo:

```
  receiver      : guardia-webhook
  alerta    : TasaErrorAlta
  severidad : critical
  detalle   : La proporcion de ordenes fallidas es 25.3% en los ultimos 5 minutos (umbral: 10%).
```

Fíjate en tres cosas:

1. **`receiver : guardia-webhook`**. En la prueba del Paso 12 ya llegó por este camino. Nadie
   le ha dicho a mano a dónde enviarla: **el árbol de rutas vio `critical` y eligió**.
2. **`25.3%`: ese número no lo escribió nadie.** La plantilla `{{ printf "%.1f" $value }}`
   lo rellenó al disparar. Y no es 30, porque la ventana de 5 minutos todavía mezcla datos
   de cuando fallaba el 5 %.
3. **Nadie escribió este aviso.** Lo produjeron una regla de pocas líneas, un árbol de
   rutas y un receptor. Tú solo cambiaste un número.

**En tu Gmail**, unos segundos después: un correo con `[FIRING:1] TasaErrorAlta`. Llega
algo más tarde porque la ruta del correo espera 30 segundos y la crítica, 10.

**En Alertmanager** (`http://localhost:9093`): la alerta aparece **dos veces**, una en el
grupo de `guardia-webhook` y otra en el de `equipo-datos-email`.

**Alertmanager agrupa por receptor.** Esas dos apariciones son la prueba visual del
`continue: true`: sin él, solo verías la del webhook y nunca te llegaría el correo.

> **Prometheus enseña todo lo que vigila. Alertmanager solo enseña lo que tiene que
> avisar.** Por eso aquí no aparecen las cuatro reglas.

### Paso 21 — Silenciar durante un mantenimiento

Hazlo **ahora, con la alerta en rojo**, para ver su efecto.

**La situación:** vas a hacer un mantenimiento en el processor y sabes que fallará durante
un rato. No quieres que el equipo reciba avisos de algo que ya sabes.

En `http://localhost:9093` pulsa **New Silence** y rellena:

| Campo | Qué escribir |
|---|---|
| **Duration** | `1h` |
| **Matchers** | `service="order-processor"` |
| **Creator** | tu nombre |
| **Comment** | `mantenimiento programado` |

Pulsa **Create**.

**Cómo se escribe un matcher.** Es la condición que dice **qué alertas se silencian**, y se
escribe así, con las comillas en el valor:

```
service="order-processor"
   │    │        │
etiqueta igual  valor
```

Se lee: *«silencia todas las alertas cuya etiqueta `service` sea `order-processor`»*.
**Se puede silenciar por `service` porque es una etiqueta**, no un texto de la descripción.

> Si tu pantalla muestra dos casillas separadas (*Name* y *Value*), escribe `service` en la
> primera y `order-processor` en la segunda. El significado es el mismo.

**Comprueba el efecto en los dos programas:**

| Dónde | Qué verás |
|---|---|
| `http://localhost:9093` | `TasaErrorAlta` **ya no aparece**. Alertmanager oculta lo silenciado; marcando la casilla **Silenced** vuelve a verse. |
| `http://localhost:9090/alerts` | `TasaErrorAlta` **sigue en rojo**. |

> **El silencio no apaga la vigilancia. Solo apaga el aviso.** Prometheus no sabe nada del
> silencio: el problema sigue existiendo y registrado. Así, cuando el silencio caduque, si
> sigue roto, avisará en ese momento.
>
> **Analogía:** silenciar el móvil en una reunión. Las llamadas siguen entrando y quedan
> registradas; simplemente no suena.

**Por qué silenciar y no borrar la regla:** el silencio **caduca solo** y queda escrito quién
lo puso y por qué. Una regla borrada depende de que alguien se acuerde de volver a ponerla.

**Ahora quita el silencio**, antes de arreglar el incidente: si el problema se resolviera con
el silencio puesto, **tampoco llegaría el aviso de «resuelto»**. En la pestaña **Silences**,
busca el tuyo y pulsa **Expire**.

### Paso 22 — Resolver el incidente

En `.env`, vuelve a:

```
ERROR_RATE_PCT=5
```

Guarda y aplica:

```powershell
docker compose up -d order-processor; docker compose exec order-processor printenv ERROR_RATE_PCT
```

**Qué esperamos:** **`5`**.

En `http://localhost:9090/alerts`, `TasaErrorAlta` **pasará de rojo a verde sin pasar por
amarillo**. El `for` solo existe para confirmar que un problema es real **antes de avisar**;
para darlo por arreglado no hace falta esperar.

**Y después llegarán los avisos de «resuelto»**: en el webhook, `status global : resolved`,
y en Gmail, `[RESOLVED] TasaErrorAlta`.

**Ten paciencia: puede tardar entre 5 y 10 minutos desde el cambio.** Hay tres esperas
encadenadas, y conviene conocerlas para no pensar que algo falló:

| Espera | Motivo | Duración |
|---|---|---|
| **1. Que baje el porcentaje** | La regla mide los últimos 5 minutos; los fallos de antes siguen contando hasta que salen de esa ventana | 2 a 4 min |
| **2. Que el detector lo note** | Prometheus revisa cada 15 s | segundos |
| **3. Que salga el aviso** | `group_interval: 5m`: Alertmanager revisa el grupo **cada 5 minutos contados desde su primer aviso**, no desde que se arregló | hasta 5 min |

**Analogía de la tercera espera:** un autobús que pasa cada 5 minutos. Aunque llegues a la
parada justo después de que se vaya, esperarás al siguiente.

> **«Ya está en verde y no llega nada» es la duda más común de esta sesión.** Detectar y
> avisar son dos momentos distintos: el verde lo decide Prometheus; el aviso, Alertmanager,
> en su siguiente turno.

**Un detalle que parece un error y no lo es.** Mira el `detalle` del aviso de «resuelto»:

```
estado  : resolved
detalle : La proporcion de ordenes fallidas es 10.1% ... (umbral: 10%)
```

Dice **resuelto**, pero 10,1 % está **por encima** del umbral. No es una contradicción: el
texto se calcula con **el último valor que tenía la alerta mientras estaba activa**. Cuando
el porcentaje bajó del 10 %, la alerta dejó de evaluarse y el texto quedó congelado en su
último dato. **En un aviso de «resuelto», el número es el último que se midió antes de
resolverse, no el valor actual.**

### Lo que le falta al receptor para un entorno real

Acabas de ver el ciclo completo. Antes de seguir, conviene tener claro qué le falta al
receptor de hoy para ir más allá de un curso. Su propio registro lo avisa al arrancar:

```
WARNING: This is a development server. Do not use it in a production deployment.
```

| Qué falta | Por qué importa |
|---|---|
| **Autenticación** | Tal como está, cualquiera que alcance esa dirección puede enviarle alertas falsas. Se protege con un secreto compartido o dejándolo accesible solo desde la red interna. |
| **Cifrado** | Si el tráfico sale de la red interna, una alerta puede llevar nombres de servidores, rutas o identificadores, y viajaría sin proteger. |
| **Un servidor preparado** | El servidor de desarrollo de Flask atiende de uno en uno y no está pensado para aguantar carga. |
| **Disponibilidad** | Si el receptor se cae, Alertmanager reintenta un rato, pero un receptor caído acaba siendo una alerta que nadie ve. **Hay que vigilar al vigilante.** |
| **Guardar fuera del contenedor** | Lo que imprime y su archivo `/tmp/alertas_recibidas.log` **se pierden cuando el contenedor se recrea**. Un receptor real guarda cada alerta en un sistema externo: una base de datos o el sistema de incidencias. |

Y una pregunta que hay que hacerse siempre antes de enviar una alerta a cualquier sitio:
**¿qué datos lleva dentro y quién va a poder leerlos?**

> **En una frase:** el correo sirve para **avisar a personas**; el webhook, para que **un
> sistema reaccione**. En cuanto un equipo tiene guardias, registro de incidencias o procesos
> que automatizar, lo segundo deja de ser opcional, y el punto de entrada es exactamente lo
> que has montado hoy.

---

## Bloque 6 — La misma alerta, al estilo Grafana

Prometheus no es el único que sabe evaluar alertas. Grafana también puede hacerlo, y
compararlos con el mismo caso enseña mucho sobre los dos.

### Paso 23 — Instalar la alerta de Grafana

> 📄 Archivo del LMS: **`orderflow-alerts.yml`** → es para **Grafana**, no para Prometheus.

Grafana lee al arrancar la carpeta `grafana/provisioning`, que ya usaste en la Sesión 4.
Cada subcarpeta es un **cajón con un tipo de contenido fijo**:

| Carpeta | Qué busca Grafana ahí | Desde |
|---|---|---|
| `datasources` | De dónde saca los datos | Sesión 4 |
| `dashboards` | Qué paneles cargar | Sesión 4 |
| `alerting` | **Qué alertas evaluar y a quién avisar** | Hoy |

Si el archivo estuviera en otro cajón, **Grafana lo ignoraría sin avisar**.

```powershell
New-Item -ItemType Directory -Force -Path grafana\provisioning\alerting | Out-Null; Copy-Item "$HOME\Downloads\orderflow-alerts.yml" grafana\provisioning\alerting\; Get-ChildItem grafana\provisioning
```

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
mkdir -p grafana/provisioning/alerting && cp ~/Downloads/orderflow-alerts.yml grafana/provisioning/alerting/ && ls grafana/provisioning
```

</details>

**Qué esperamos:** tres carpetas, `alerting`, `dashboards` y `datasources`.

Grafana solo revisa esas carpetas **al arrancar**, así que reinícialo:

```powershell
docker compose restart grafana
```

Aquí basta `restart`: no cambiaste `docker-compose.yml`, solo añadiste un archivo dentro de
una carpeta que Grafana ya tenía montada.

**Espera unos 20 segundos** y mira si cargó el archivo:

```powershell
docker compose logs grafana --tail 80 | Select-String "provisioning.alerting"
```

**Qué esperamos:** dos líneas seguidas, sin error entre medias:

```
logger=provisioning.alerting ... msg="starting to provision alerting"
logger=provisioning.alerting ... msg="finished to provision alerting"
```

> **Sobre los `level=error` que ya conoces de la Sesión 4.** Grafana revisa todos sus
> cajones posibles y avisa de los que no existen. Los de `plugins` y `notifiers` seguirán
> apareciendo y **son normales**. El de `alerting`, `can't read alerting provisioning files`,
> desaparece a partir de hoy, porque acabas de crear esa carpeta.

### Paso 24 — Entender el archivo

Abre `grafana/provisioning/alerting/orderflow-alerts.yml` en VS Code. Tiene **tres partes**,
numeradas en sus comentarios, y equivalen a lo que ya conoces:

| Parte del archivo | Qué decide | Equivale a |
|---|---|---|
| **1) `contactPoints`** | **A quién** avisar | Los `receivers` de Alertmanager |
| **2) `policies`** | **Cómo** agrupar y cada cuánto repetir | El `route` de Alertmanager |
| **3) `groups`** | **Qué** vigilar | Las reglas de `prometheus/alerts.yml` |

#### 1) El punto de contacto

| Línea | Qué significa |
|---|---|
| `orgId: 1` | La organización de Grafana a la que pertenece. Grafana puede tener varias, como departamentos separados; la 1 es la de fábrica. |
| `name: equipo-datos` | El nombre que verás en pantalla. La política lo usa para decir «envía aquí». |
| `uid: cp-webhook-guardia` | Un identificador fijo, como el `uid: prometheus` de la Sesión 4. Sin él, Grafana inventaría uno distinto en cada instalación. |
| `type: webhook` | El tipo de canal. |
| `url: http://webhook-receiver:5001/alertas` | **El mismo receptor que usa Alertmanager.** |
| `disableResolveMessage: false` | Escrito «al revés»: `false` significa **no desactivar** el aviso de resuelto. |

> **Cuidado con esa última línea.** Alertmanager pregunta *«¿envío el resuelto?»*
> (`send_resolved: true` = sí). Grafana pregunta *«¿desactivo el resuelto?»*
> (`disableResolveMessage: false` = no). Las dos configuraciones hacen lo mismo.

**Por qué Grafana avisa al webhook y no al correo:** configurar Gmail en Alertmanager **no le
da correo a Grafana**. Son programas distintos, y Grafana tendría que tener su propia
configuración de correo (es el **Ejercicio D**). Enviarlo al mismo receptor demuestra algo
más interesante: **dos sistemas distintos pueden avisar al mismo punto de entrada**.

#### 2) La política

`receiver: equipo-datos`, `group_by`, `group_wait: 30s`, `group_interval: 5m` y
`repeat_interval: 3h` significan lo mismo que en Alertmanager.

#### 3) La regla

| Línea | Qué significa |
|---|---|
| `folder: OrderFlow` | La carpeta donde aparecerá, la misma de tu dashboard. |
| `interval: 1m` | Grafana evalúa la regla **cada minuto** (Prometheus lo hace cada 15 s). |
| `condition: C` | Cuál de los pasos de `data` decide si hay alerta. |
| `for: 2m` | La misma paciencia que en Prometheus. |
| `noDataState: OK` | Qué hacer si la consulta **no devuelve datos**. Se explica abajo. |
| `execErrState: Alerting` | Si la consulta **da error** (por ejemplo, Prometheus no responde), avisa. |
| `labels` | `severity: critical` y `service: order-processor`, **iguales que en Prometheus**. |
| `annotations` | El resumen y la descripción. |

**La condición, partida en tres pasos.** Prometheus la escribe en una línea; Grafana la separa
en bloques que se ven en pantalla:

| Paso | Qué hace | Analogía |
|---|---|---|
| **A** | La consulta: la misma expresión, **sin el umbral** | Tomar la temperatura varias veces durante 10 minutos |
| **B** | *Reduce*: se queda con **un solo número**, el último | Quedarse con la última medición |
| **C** | *Threshold*: compara ese número con `10` | Preguntar «¿pasa de 10?» |

**¿Por qué hace falta el paso B?** La consulta A devuelve una **serie** de valores en el
tiempo, y un umbral solo puede comparar **un número**. Primero hay que elegir qué valor se
compara.

**El valor en el texto del aviso.** La descripción usa:

```
{{ printf "%.1f" $values.B.Value }}
```

`$values.B.Value` es **el número que calculó el paso B**. Es el equivalente de Grafana al
`{{ $value }}` de Prometheus: gracias a él, el aviso dice *cuánto* está fallando y no solo
*que* está fallando.

**Por qué `noDataState: OK`.** Esta línea tiene una historia que conviene conocer, porque es
un error muy común en entornos reales.

Si el processor se apaga, la consulta de la regla **se queda sin datos**. Con la opción por
defecto (`NoData`), Grafana dispara una alerta especial llamada `DatasourceNoData`, y lo hace
**reutilizando los textos de la regla**. El aviso llega así:

```
alerta    : DatasourceNoData
severidad : critical
resumen   : Tasa de error > 10% (regla nativa de Grafana)
```

Imagina recibirlo a las tres de la mañana: dice que **la tasa de error pasa del 10 %**, y vas a
buscar pedidos con errores... que no existen. El processor no está fallando pedidos: **está
apagado**. El aviso te manda a buscar en el sitio equivocado, y además repite lo que ya dice
`ProcessorCaido`, que avisa de la causa real. En las pruebas de este curso, tampoco llegó
nunca su aviso de «resuelto»: un receptor que abriera incidencias habría dejado una abierta
para siempre.

`OK` significa *«sin datos, no avises»*, porque de la caída ya se encarga `ProcessorCaido`.

> **La lección que vale para cualquier herramienta:** con la misma condición, la regla de
> Prometheus se queda **callada** cuando no hay datos, y la de Grafana, por defecto, **avisa**.
> Ninguno de los dos comportamientos es correcto siempre. **Para cada alerta hay que decidir
> qué significa «no tengo datos»** y comprobar que otra alerta cubre ese caso.
>
> Y un detalle más: la inhibición de Alertmanager **no puede silenciar a Grafana**. Grafana
> no pasa por Alertmanager; tiene su propio sistema de avisos.

### Paso 25 — Verla en Grafana

Abre Grafana (`http://localhost:3000`) → **menú ☰ → Alerting**:

1. **Alert rules:** en la carpeta `OrderFlow`, grupo `orderflow_grafana`, la regla
   **`TasaErrorAlta (Grafana)`** en estado **Normal** y con la marca **Provisioned** (viene de
   un archivo). Pulsa sobre ella y **View**: verás los pasos **A**, **B** y **C**.
2. **Contact points:** `equipo-datos`, de tipo **Webhook**.

### Paso 26 — Probar el canal de Grafana

El mismo gesto del Paso 12: comprobar que suena el timbre.

Con la pestaña del webhook escuchando, en **Contact points** abre `equipo-datos` (**View** o
**Edit**), pulsa **Test** y después **Send test notification**.

**Qué esperamos en la pestaña del webhook:**

```
  receiver      : test
  alerta    : TestAlert
  severidad : None
  servicio  : None
  resumen   : Notification test
172.18.0.x - - [...] "POST /alertas HTTP/1.1" 200 -
```

Los `None` son normales: la alerta de prueba de Grafana no trae las etiquetas de **tu** regla.
Lo que importa es que **llegue**.

**Fíjate en la dirección del final de la línea.** Es distinta de la de los avisos de
Alertmanager: **son dos programas distintos hablando con el mismo receptor**, y al receptor le
da igual quién le escriba.

### Paso 27 — Dos detectores, un problema

Repite el incidente para ver a los dos detectores a la vez.

En `.env`, `ERROR_RATE_PCT=30`, y:

```powershell
docker compose up -d order-processor; docker compose exec order-processor printenv ERROR_RATE_PCT
```

Abre dos pestañas del navegador y refresca cada 30 segundos:

| Pestaña | Dónde | Qué mirar |
|---|---|---|
| Prometheus | `http://localhost:9090/alerts` | `TasaErrorAlta` |
| Grafana | **Alerting → Alert rules** | `TasaErrorAlta (Grafana)` |

Las dos pasarán por **Pending** y **Firing**. **Grafana suele ir un poco por detrás**, porque
evalúa cada minuto y Prometheus cada 15 segundos: son dos vigilantes que hacen la ronda con
distinta frecuencia.

**Qué esperamos en la pestaña del webhook:** dos avisos del mismo problema, con pocos
segundos de diferencia:

| | Aviso de Alertmanager | Aviso de Grafana |
|---|---|---|
| `receiver` | `guardia-webhook` | `equipo-datos` |
| `alerta` | `TasaErrorAlta` | `TasaErrorAlta (Grafana)` |
| `severidad` / `servicio` | `critical` / `order-processor` | `critical` / `order-processor` |
| `detalle` | con el porcentaje | con el porcentaje |

> **Las etiquetas coinciden porque se escribieron igual en las dos reglas.** Por eso un
> receptor real podría tratar los dos avisos con la misma lógica, sin importar de qué
> herramienta vengan. Si las etiquetas fueran distintas en cada herramienta, habría que
> programar dos veces lo mismo.

**Resuelve el incidente:** `ERROR_RATE_PCT=5` en `.env` y el mismo comando de antes, hasta ver
`5`. En unos minutos llegarán los dos «resuelto».

**Prometheus y Grafana no compiten:** Prometheus evalúa pegado al dato y reparte los avisos con
Alertmanager; Grafana puede alertar sobre métricas **y logs** desde la misma herramienta donde
está el panel.

### Paso 28 — Validar la sesión

```powershell
python scripts/validate_sesion5.py
```

Si cambiaste la contraseña de Grafana y no está en tu `.env`, pásala solo para esta pestaña
(no queda guardada en ningún archivo):

```powershell
$env:GRAFANA_ADMIN_PASSWORD = "tu_contraseña_de_grafana"; python scripts/validate_sesion5.py
```

**Qué esperamos:** nueve comprobaciones en **OK** y el Ejercicio B en **PEND** hasta que lo
hagas.

| Comprobación | Qué mira |
|---|---|
| Reglas de alerta cargadas | Las cuatro reglas en Prometheus |
| Las métricas de las reglas existen | Que ninguna regla use un nombre de métrica inventado |
| Prometheus conoce un Alertmanager | El bloque `alerting` de `prometheus.yml` |
| Alertmanager: receivers e inhibición | Los dos receptores y la regla de inhibición |
| La ruta final no filtra por severidad | El fallo silencioso del Bloque 3 |
| Correo sin contraseña a la vista | `smtp_auth_password_file`, sin contraseña escrita, archivo protegido por `.gitignore`. **No lee la contraseña.** |
| webhook-receiver responde | `/health` |
| Llegó algún aviso al webhook | Que el Bloque 3 o el 5 funcionaran |
| Grafana: regla y punto de contacto | `TasaErrorAlta (Grafana)` y `equipo-datos` |

---

## Ejercicios (haz estos tú solo)

Las respuestas escritas de los ejercicios B y C van en tu entregable
(`scripts/entregable_template.md`).

> **Los ejercicios A y B apagan el processor.** Si los haces seguidos, puedes aprovechar el
> mismo apagado. Al terminar, enciéndelo con `docker compose start order-processor`.

### Ejercicio A — Lee lo que llega

Con una alerta disparada, pregunta a Alertmanager qué alertas tiene activas y averigua **a qué
receptores** se envió cada una y **cuántas** hay.

Para tener una alerta disparada rápido, apaga el processor y espera a que `ProcessorCaido` esté
en rojo en `http://localhost:9090/alerts` (algo más de un minuto):

```powershell
docker compose stop order-processor
```

Después pregunta a Alertmanager:

```powershell
Invoke-RestMethod http://localhost:9093/api/v2/alerts | ConvertTo-Json -Depth 5
```

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
curl -s http://localhost:9093/api/v2/alerts
```

</details>

**Qué hace cada parte:**

| Parte | Qué hace |
|---|---|
| `/api/v2/alerts` | La «ventanilla» de Alertmanager donde los **programas** preguntan por las alertas activas. El validador de la sesión usa esta misma ventanilla. |
| `Invoke-RestMethod` | Hace la pregunta y convierte la respuesta en objetos de PowerShell. |
| `ConvertTo-Json -Depth 5` | Devuelve la respuesta a su formato original, **el mismo JSON que llega al webhook**. `-Depth 5` muestra hasta cinco niveles de datos unos dentro de otros. |

> **Por qué `ConvertTo-Json`.** Sin él, PowerShell muestra los datos «apretados», con formas
> como `@{name=guardia-webhook}` o `System.Object[]`, que parece un error y en realidad
> significa **lista vacía**.

**Pistas para leer la respuesta:**

- Cada alerta tiene un campo **`receivers`** y otro **`status`**.
- **`"value"` y `"Count"` no vienen de Alertmanager**: los añade PowerShell al convertir una
  lista. `Count` te dice cuántas alertas hay.
- **`\u0026`** es el símbolo `&` protegido.
- **`endsAt` tiene una hora en el futuro:** no es cuándo terminará, sino una **fecha de
  caducidad** que Prometheus renueva cada vez que confirma la alerta. Ejecuta el comando dos
  veces con un minuto de diferencia y compáralas.
- **En `labels` hay etiquetas que no están en la regla** (`job`, `instance`, `monitor`,
  `component`): las añade Prometheus. **Las etiquetas de una alerta son las de la regla más las
  del dato que la produjo.**
- **El enlace de `generatorURL` no abre en tu navegador:** usa el nombre interno del contenedor
  de Prometheus.

Anota el nombre de cada receptor y el número de alertas activas.

### Ejercicio B — Escribe la quinta regla

Al final de `prometheus/alerts.yml` hay un bloque `TODO (Sesion 5)`. Escribe ahí, **debajo del
comentario y alineada con los otros `- alert:`**, la regla `SinOrdenesProcesadas`:

- **Condición:** no se ha procesado ninguna orden en los últimos 10 minutos.
- **`for`:** `10m`
- **`severity`:** `warning`
- **`service`:** `order-processor`

*Pista 1: si el processor está encendido pero no procesa nada, la tasa de su contador vale
exactamente 0. El nombre de la métrica está en `docs/metricas.md`.*

*Pista 2: si el processor está **apagado**, Prometheus no puede leer la métrica, y la tasa no
vale 0: **queda vacía**. «Vacío == 0» nunca es verdad. Para cubrir los dos casos, une tu
expresión con `or` a `absent_over_time(...[10m])`, que vale 1 cuando la métrica no ha dado
ningún dato en esos 10 minutos.*

Valida, recarga y provoca el atasco:

```powershell
docker run --rm --entrypoint promtool -v "${PWD}/prometheus:/cfg" prom/prometheus:v2.51.0 check rules /cfg/alerts.yml
```

**Qué esperamos:** `SUCCESS: 5 rules found`.

```powershell
Invoke-RestMethod -Method Post http://localhost:9090/-/reload; docker compose stop order-processor
```

Observa `http://localhost:9090/alerts`. **Ten paciencia: tardará unos 20 minutos**, porque la
ventana de 10 minutos tiene que quedarse sin datos y después hay que cumplir los 10 minutos
del `for`. Cuando termines, `docker compose start order-processor`.

**Lo interesante viene después.** Al parar el processor disparas **dos** alertas del mismo
servicio: `ProcessorCaido` (critical) y la tuya (warning). Mira Alertmanager, con la casilla
**Inhibited** marcada, y explica en dos líneas **por qué solo se avisa de una**.

### Ejercicio C — Diseña un umbral

Elige **una** de las cuatro reglas de `alerts.yml` y responde en tres o cuatro líneas:

- ¿Por qué ese umbral y no uno más alto o más bajo?
- ¿Qué pasaría si el `for` fuera de 10 segundos en vez de lo que tiene?
- Si esta alerta sonara tres veces por semana, **y en ninguna de esas veces hubiera un problema
  real**, ¿qué harías: subir el umbral, alargar el `for`, bajarle la severidad o borrarla?
- ¿Qué debería hacer esta alerta si el servicio que mide **deja de enviar datos**? ¿Hay otra
  alerta que ya cubra ese caso?

*No hay una respuesta única. Lo que se practica aquí es el criterio: una alerta que nadie
atiende no es una alerta, es ruido, y el ruido hace que también se ignoren las buenas.*

### Ejercicio D — Que Grafana también avise por correo

La alerta de Grafana solo avisa al webhook. Consigue que **además** llegue a tu Gmail. No te
damos las líneas: con lo aprendido hoy tienes todo lo necesario.

**Lo que tienes que resolver:**

1. **Darle a Grafana su propia configuración de correo.** Grafana se configura con variables de
   entorno en la sección `environment:` de su servicio en `docker-compose.yml`. Las que
   necesitas empiezan por `GF_SMTP_`:

   | Variable | Qué le dice a Grafana |
   |---|---|
   | `GF_SMTP_ENABLED` | Que active el envío de correo |
   | `GF_SMTP_HOST` | El servidor de salida y su puerto (el mismo de Alertmanager) |
   | `GF_SMTP_USER` | Con qué usuario se identifica |
   | `GF_SMTP_FROM_ADDRESS` | Quién aparece como remitente |
   | `GF_SMTP_PASSWORD__FILE` | **Dónde está la contraseña** |

2. **No escribir la contraseña en ningún sitio nuevo.** Fíjate en la terminación **`__FILE`**
   (dos guiones bajos): es la versión de Grafana del `_file` de Alertmanager. Puedes **reutilizar
   el mismo archivo `alertmanager/smtp_password`** montándolo también en Grafana con un volumen
   de solo lectura. Piensa en qué ruta **dentro del contenedor** le das y usa esa misma en la
   variable. Ojo: no puede quedar dentro de `/etc/grafana/provisioning`, que ya está montado
   como solo lectura.

3. **Añadir el correo al punto de contacto.** Un punto de contacto puede tener **varios
   canales** en su lista `receivers`. Añade uno de `type: email` con su propio `uid` y, en
   `settings`, la dirección en `addresses`.

4. **Aplicar y probar.** Como cambias `docker-compose.yml`, piensa si basta `restart` o hace
   falta `up -d`. Después usa el botón **Test** del punto de contacto.

**Para tu entregable:** explica en dos o tres líneas por qué la contraseña no debe escribirse
en `docker-compose.yml`, aunque ese archivo esté en tu equipo.

---

## Si algo falla

| Síntoma | Causa probable | Solución |
|---|---|---|
| `git check-ignore` no devuelve nada | Falta la línea en `.gitignore` | Añádela con el comando del Paso 3 antes de seguir |
| No llega el correo y el registro de Alertmanager dice `535` o `Username and Password not accepted` | Contraseña de aplicación incorrecta o con espacios | Crea otra en `myaccount.google.com/apppasswords` y pégala sin espacios |
| No llega el correo y no hay error | Está en spam, o la ruta final tiene condiciones | Revisa spam; la última ruta debe ir sin `matchers` |
| En tu disco, `alertmanager/smtp_password` es una **carpeta** y no un archivo | Se levantó el stack con el volumen antes de crear el archivo | `docker compose stop alertmanager`, borra esa carpeta, crea el archivo (Paso 2) y `docker compose up -d alertmanager` |
| `alertmanager: error: unexpected amtool` | Falta `--entrypoint amtool` | Copia el comando del Paso 10 |
| `webhook-receiver` no arranca | La imagen no se construyó | `docker compose up -d --build webhook-receiver` |
| `failed to read dockerfile` al construir | Los tres archivos no están en `services/webhook-receiver/` | Revisa el Paso 5 |
| Prometheus no muestra las reglas | No recargaste, o el YAML está mal | `promtool` del Paso 13 y `docker compose logs prometheus --tail 30` |
| La alerta nunca pasa de `Inactive` | La métrica no existe o `ERROR_RATE_PCT` no se aplicó | Pega la `expr` en **Graph**; comprueba con `printenv` |
| La alerta tarda muchísimo en disparar | Es normal | `rate([5m])` + `for: 2m` suman varios minutos reales |
| Está en verde y no llega el «resuelto» | `group_interval: 5m` | Espera hasta 10 minutos (Paso 22) |
| Cambié `.env` y no pasa nada | Falta recrear el contenedor | `docker compose up -d order-processor` |
| No aparece `TasaErrorAlta (Grafana)` | El archivo no está en `grafana/provisioning/alerting/` o Grafana no se reinició | Revisa el Paso 23 |
| La búsqueda en el registro de Grafana sale vacía | El reinicio quedó fuera de las líneas revisadas | Aumenta el número de `--tail` |
| El validador dice `credenciales de Grafana incorrectas` | Cambiaste la contraseña de Grafana | Usa `$env:GRAFANA_ADMIN_PASSWORD` (Paso 28) |
| La pestaña del webhook no muestra los avisos de antes | El contenedor se recreó (por ejemplo, tras apagar el equipo) | Normal: su registro vive dentro del contenedor |

Para cualquier otro problema: `docs/troubleshooting.md`.

---

## Antes de la Sesión 6

1. **Deja `ERROR_RATE_PCT` en `5`, y compruébalo en los dos sitios:**

   ```powershell
   Select-String -Path .env -Pattern "ERROR_RATE_PCT"; docker compose exec order-processor printenv ERROR_RATE_PCT
   ```

   Deben salir `ERROR_RATE_PCT=5` y `5`. El archivo y el programa pueden no coincidir si
   cambiaste uno y no recreaste el otro. La Sesión 6 analiza los datos acumulados; con un 30 %
   de errores, los informes parecerían un problema grave.

2. **Baja el stack sin `-v`:**

   ```powershell
   docker compose down
   ```

   | Comando | Qué hace | Analogía |
   |---|---|---|
   | `stop` | Apaga los contenedores y los deja ahí | Apagar la radio |
   | `down` | Apaga los contenedores y **los retira**, junto con la red | Desenchufarla y guardarla en el armario |
   | `down -v` | Además **borra los datos guardados** (volúmenes) | Guardarla y **tirar tus discos** |

   Los volúmenes guardan los pedidos, el histórico de métricas, los logs y tu Grafana. **La
   Sesión 6 los necesita.** Lo que **sí** se pierde con `down` es lo que vive dentro de los
   contenedores, como el registro del receptor: la misma lección del Bloque 5.

3. **Descarga de la plataforma** los cinco archivos de la Sesión 6: los cuatro notebooks
   `.ipynb` y su `requirements.txt`.

4. **Completa el entregable** con la plantilla `scripts/entregable_template.md`.

> En la Sesión 6 dejas de mirar por pantalla. Vas a consultar Prometheus y Elasticsearch desde
> Python, y a construir un informe de salud del pipeline que se genera solo.
