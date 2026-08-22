# Manual de práctica — Sesión 2

## Métricas con Prometheus y exporters

**Capítulo 1:** Observabilidad y captura de datos operativos

> Las diapositivas explican la teoría; los comandos y las consultas salen de aquí.
> Si una consulta de la pantalla no coincide con este documento, manda este documento.

---

## Qué vas a construir hoy

Hoy el stack **crece por primera vez**: pasa de 10 a 13 servicios. Y los añades
**tú**, escribiéndolos en tu propio `docker-compose.yml`.

Los tres nuevos resuelven un problema concreto. Postgres y Redis no son código
nuestro: no podemos abrirlos y añadirles métricas. Necesitamos un **traductor**
que hable su idioma nativo y publique lo que ve en el formato que Prometheus
entiende. Eso es un *exporter*.

Al terminar la sesión tendrás:

1. `postgres-exporter` y `redis-exporter` publicando el estado interno de tu base de datos y tu cola.
2. `pushgateway` recibiendo métricas de scripts que viven pocos segundos.
3. Prometheus scrapeando 6 targets en lugar de 3.
4. Una métrica de negocio escrita por ti, en Python.

**Nada de lo de la Sesión 1 se toca.** Los 10 servicios que ya tenías siguen
exactamente igual. Ésta es la regla del curso: cada sesión suma, ninguna resta.

---

## Punto de partida

Antes de empezar, confirma que vienes de una Sesión 1 sana:

```bash
docker compose up -d
docker compose ps
```

**Qué debes ver:** 10 filas, todas `Up` o `healthy`.

Si algo falla aquí, resuélvelo antes de continuar. Todo lo de hoy se apoya en eso.

> **Todo lo que construyas hoy vive en tu equipo.** No hay nada que descargar: a
> partir de esta sesión, tu repositorio y el del docente empiezan a separarse, y
> eso es lo correcto. El tuyo crece con tu trabajo.

---

## Dónde se escribe cada cosa

Este manual mezcla tres sitios distintos. Antes de empezar, ten claro cuál es cuál:

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

## Bloque 1 — Hacer crecer el stack

### Paso 1 — Abrir el archivo que define tu stack

Abre `docker-compose.yml` en VS Code. Es el archivo que dice qué servicios
existen y cómo se conectan entre sí.

Baja **hasta el final del archivo**. La última sección que verás es `kibana:`,
que termina así:

```yaml
    depends_on:
      elasticsearch:
        condition: service_healthy
```

Ahí es donde vas a escribir. Deja una línea en blanco después.

### Paso 2 — Añadir los tres servicios

Copia este bloque completo y pégalo al final del archivo.

> **Acuérdate del apartado «Cómo pegar los bloques de código sin romperlos».**
> Los nombres de servicio (`postgres-exporter:`) llevan **2 espacios** delante,
> igual que el `kibana:` que tienes justo encima. Si al pegar quedan pegados al
> margen, selecciona el bloque y pulsa `Tab`. El Paso 3 está precisamente para
> cazar esto, así que no te preocupes si dudas: ahora lo comprobamos.

```yaml
  # ============================================================
  # SESION 2 - Exporters y Pushgateway
  # ============================================================
  # Un exporter es un traductor: habla el protocolo nativo de un
  # servicio (Postgres, Redis) y publica sus metricas internas en
  # el formato que Prometheus sabe leer. Sirven para monitorear
  # software que no podemos instrumentar porque no es nuestro.
  # ============================================================

  # Traduce las metricas internas de Postgres (conexiones, tamano
  # de base, transacciones, locks). Reutiliza las credenciales que
  # ya estan en .env: no hay que crear un usuario nuevo.
  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:v0.15.0
    container_name: orderflow-postgres-exporter
    restart: unless-stopped
    environment:
      DATA_SOURCE_NAME: "postgresql://${POSTGRES_USER:-orderflow}:${POSTGRES_PASSWORD:-orderflow_dev_2026}@postgres:5432/${POSTGRES_DB:-orderflow_dw}?sslmode=disable"
    ports:
      - "${POSTGRES_EXPORTER_PORT:-9187}:9187"
    networks:
      - orderflow-net
    depends_on:
      postgres:
        condition: service_healthy

  # Mismo patron, para Redis: memoria usada, clientes conectados,
  # comandos por segundo, longitud de las listas.
  redis-exporter:
    image: oliver006/redis_exporter:v1.62.0
    container_name: orderflow-redis-exporter
    restart: unless-stopped
    environment:
      REDIS_ADDR: "redis://redis:6379"
    ports:
      - "${REDIS_EXPORTER_PORT:-9121}:9121"
    networks:
      - orderflow-net
    depends_on:
      redis:
        condition: service_healthy

  # Buzon intermedio para trabajos de corta duracion (batch, cron,
  # ETL). Prometheus no alcanza a scrapear un script que vive 3
  # segundos, asi que el script empuja su metrica aqui y Prometheus
  # lee este servicio, que si esta siempre en pie.
  pushgateway:
    image: prom/pushgateway:v1.9.0
    container_name: orderflow-pushgateway
    restart: unless-stopped
    ports:
      - "${PUSHGATEWAY_PORT:-9091}:9091"
    networks:
      - orderflow-net
```

Guarda el archivo con `Ctrl+S`.

Antes de seguir, fíjate en tres cosas del `postgres-exporter`:

- **No expone Postgres**: expone métricas *sobre* Postgres, en el puerto 9187.
- **`DATA_SOURCE_NAME`** apunta a `postgres:5432`, el nombre del servicio en la red interna de Docker. No `localhost`: dentro de un contenedor, `localhost` es él mismo.
- **Reutiliza las credenciales de `.env`.** No hay que crear ningún usuario nuevo.

### Paso 3 — Comprobar que lo escribiste bien

En YAML, un espacio de más rompe el archivo. Compruébalo antes de levantar nada:

```bash
docker compose config --services
```

**Qué debes ver:** 13 nombres. Los 10 de siempre más `postgres-exporter`,
`redis-exporter` y `pushgateway`.

> **Si sale un error de sintaxis**, casi siempre es la indentación. Los nombres
> de servicio (`postgres-exporter:`) llevan **2 espacios**; sus propiedades
> (`image:`) llevan **4**; los elementos de lista (`- orderflow-net`) llevan
> **6**. Compáralo con el servicio `kibana` que tienes justo encima.

### Paso 4 — Levantar solo lo nuevo

```bash
docker compose up -d
```

**Qué debes ver** — y esto es lo importante de hoy:

```
orderflow-postgres          Running
orderflow-redis             Running
...
orderflow-postgres-exporter  Created  →  Started
orderflow-redis-exporter     Created  →  Started
orderflow-pushgateway        Created  →  Started
```

Los que ya existían dicen **`Running`**: Docker los deja en paz. Solo los tres
nuevos dicen `Created`. Ése es el comportamiento incremental que vas a ver en
todas las sesiones.

```bash
docker compose ps
```

**Qué debes ver:** 13 filas.

### Paso 5 — Comprobar que los exporters hablan

Un exporter no envía nada a nadie: **cuelga un boletín en una dirección y lo deja
ahí**. Vas a leerlo tú a mano, poniéndote en el lugar de Prometheus.

La forma más sencilla es abrir las dos direcciones en el navegador:

```
http://localhost:9187/metrics
http://localhost:9121/metrics
```

Si prefieres la terminal, en **PowerShell**:

```powershell
(Invoke-WebRequest -UseBasicParsing http://localhost:9187/metrics).Content -split "`n" | Select-Object -First 20
```

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
curl -s http://localhost:9187/metrics | head -20
```

</details>

**Qué debes ver:** una pared de texto con cientos de líneas. No hay que leerla:
solo comprobar que está ahí.

Ahora fíjate en el volumen. Nuestro `order-processor` publica **5** medidas. El
exporter de Postgres publica **374**, y el de Redis **163**. La diferencia es que
nosotros elegimos las cinco que nos importaban; el exporter no elige, publica
todo lo que el servicio sabe de sí mismo.

> **Tener 374 datos no es tener 374 problemas resueltos: es tener 374 datos.** El
> resto del curso trata de quedarse con los pocos que avisan de algo antes de que
> el cliente se queje.

Busca en el boletín de Postgres, con `Ctrl+F`, la palabra `numbackends`:

```
pg_stat_database_numbackends{datname="orderflow_dw"} 3
```

Dice que hay **3 programas conectados** a la base de datos. Y solo tenemos uno
que escriba pedidos. Los otros dos son el propio exporter —que también necesita
conectarse para poder preguntar— y una conexión de reserva.

> **El que mide, también consume.** Un exporter mal configurado en producción
> puede llegar a tumbar la base de datos que intentaba vigilar.

### Paso 6 — Enseñarle los targets nuevos a Prometheus

Los exporters ya publican, pero **Prometheus todavía no los lee**. Hay que
decírselo.

Prometheus **no descubre nada por su cuenta**. Es un vigilante con una ronda
escrita en un papel: pasa por los sitios de su lista cada 15 segundos, y por
ningún otro. Un boletín colgado en un pasillo que no está en la lista puede estar
ahí meses sin servir de nada.

Lo que vas a hacer ahora es **añadir tres paradas a esa ronda**.

Abre `prometheus/prometheus.yml` en VS Code y baja al final. El último bloque es
`order-processor`. Pega esto **a continuación**:

> **La sangría otra vez.** Cada `- job_name:` lleva **2 espacios** delante. Tras
> pegar, comprueba que la primera línea nueva que empiece por `- job_name:` está
> en la misma columna que el `- job_name: order-processor` que ya tenías. Si no,
> selecciona el bloque pegado y pulsa `Tab`.

```yaml
  # ============================================================
  # SESION 2 - Exporters y Pushgateway
  # ============================================================
  # Las etiquetas service/component se anaden aqui, no en el codigo.
  # Gracias a ellas se puede consultar por capa sin conocer los
  # nombres de las metricas:  sum by (component) (...)
  # ============================================================

  # Metricas internas de Postgres, traducidas por el exporter.
  # Prometheus habla con el exporter; el exporter habla con Postgres.
  - job_name: postgres-exporter
    static_configs:
      - targets:
          - postgres-exporter:9187
        labels:
          service: postgres
          component: infrastructure

  # Metricas internas de Redis.
  - job_name: redis-exporter
    static_configs:
      - targets:
          - redis-exporter:9121
        labels:
          service: redis
          component: infrastructure

  # Pushgateway: buzon para jobs de corta duracion.
  #
  # honor_labels: true es imprescindible. La metrica llega al
  # Pushgateway con su propio label job (el del script que la envio).
  # Sin esta linea Prometheus lo sobrescribiria con job="pushgateway"
  # y se perderia la trazabilidad de que script la produjo.
  - job_name: pushgateway
    honor_labels: true
    static_configs:
      - targets:
          - pushgateway:9091
        labels:
          component: batch
```

Guarda con `Ctrl+S`.

### Paso 6b — Comprobar que lo escribiste bien

Igual que en el Paso 3 validaste el `docker-compose.yml` antes de levantarlo,
valida ahora este archivo antes de recargarlo:

```powershell
docker compose exec prometheus promtool check config /etc/prometheus/prometheus.yml
```

**Qué debes ver:**

```
SUCCESS: /etc/prometheus/prometheus.yml is valid prometheus config file syntax
```

> **Por qué este paso importa más de lo que parece.** Si el archivo estuviera mal
> escrito y recargaras igualmente, **Prometheus no se cae ni te avisa en
> pantalla**: se queda funcionando con la configuración vieja y escribe el error
> en un rincón de sus registros. Verías 3 paradas en lugar de 6, sin ninguna
> pista del motivo.
>
> Es la segunda vez hoy que aparece la misma regla: **valida antes de ejecutar**.
> Cada herramienta del curso tiene su propio validador.

### Paso 7 — Hacer que Prometheus relea su configuración

El vigilante copió la lista de paradas al empezar el turno y lleva esa copia en
el bolsillo. Acabas de cambiar la lista original, pero él sigue con la copia
vieja. Hay que decirle que la recopie.

```powershell
Invoke-WebRequest -UseBasicParsing -Method POST http://localhost:9090/-/reload
```

**Qué debes ver:** `StatusCode : 200`. Es el código que significa «recibido y
hecho», el mismo que devuelve cualquier página web que carga bien.

> **Si te sale una advertencia de seguridad** preguntando si quieres continuar,
> es que se te olvidó `-UseBasicParsing`. Ojo: **la respuesta por defecto es
> «No»**, así que si pulsas Enter sin leer, el comando se cancela y parece que
> algo se rompió.
>
> Ese parámetro le dice a PowerShell «tráeme el texto y no intentes interpretar
> la página como haría un navegador», que es justo lo que aquí no queremos.

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
curl -X POST http://localhost:9090/-/reload
```

</details>

> **La alternativa bruta** es `docker compose restart prometheus`. Funciona, pero
> es mandar al vigilante a casa y traer otro: durante el relevo **nadie vigila el
> edificio**. Y estás a ciegas justo en el momento en que acabas de tocar la
> configuración, que es cuando más probable es que algo se rompa.
>
> La recarga en caliente solo es posible porque este Prometheus arranca con el
> permiso `--web.enable-lifecycle`, que ya viene puesto en el `docker-compose.yml`
> del curso. No viene activado de fábrica: si cualquiera puede pedirle que
> recargue, cualquiera puede molestarlo.

### Paso 8 — Confirmar los 6 targets

Abre `http://localhost:9090` → **Status → Targets**.

**Qué debes ver:** 6 targets, todos en verde:

| Target | Puerto | Qué publica |
|---|---|---|
| `prometheus` | 9090 | Métricas del propio Prometheus |
| `order-generator` | 8000 | Órdenes generadas |
| `order-processor` | 8001 | Órdenes procesadas, latencia, cola |
| `postgres-exporter` | 9187 | Conexiones, transacciones, tamaño de la base |
| `redis-exporter` | 9121 | Memoria, clientes, comandos |
| `pushgateway` | 9091 | Lo que le empujen los scripts (ahora vacío) |

> **Si `postgres-exporter` sale en rojo**, casi siempre es la contraseña. Mira
> qué dice: `docker compose logs postgres-exporter --tail 20`.

Antes de seguir, fíjate en tres detalles de esa pantalla:

**1. Pone `postgres-exporter:9187`, no `localhost:9187`.** Tú abriste
`localhost:9187` en el navegador; Prometheus usa otro nombre para el mismo sitio.
Tú estás fuera del edificio y entras por la puerta de la calle; Prometheus está
dentro y usa los pasillos interiores. Mismo despacho, caminos distintos.

**2. `pushgateway` está en verde y no tiene ningún dato.** Verde solo significa
«he pasado por aquí y el boletín estaba colgado». No dice nada sobre si el
boletín tiene algo escrito. Estará vacío hasta el Bloque 3.

> **Un panel todo en verde no dice que el sistema esté bien. Dice que los sitios
> que se te ocurrió mirar respondieron.**

**3. La columna `Last Scrape` no para de reiniciarse.** Refresca la página un par
de veces y míralo. Esto no es una foto: es un bucle que no se detiene.

---

## Bloque 2 — PromQL sobre lo nuevo

Todas estas consultas se escriben en `http://localhost:9090` → **Graph**.

### Paso 9 — Descubrir qué expone un exporter

Un exporter publica cientos de medidas. Nadie se aprende esos nombres: **hay que
preguntárselos**.

En el recuadro de consulta de Prometheus (pestaña **Graph**), escribe solo esto y
espera un segundo sin pulsar nada:

```
pg_
```

Se despliega la lista de todo lo que empieza así, como el buscador del móvil.
Prueba también con `redis_`.

> **Si el nombre que buscas no aparece en esa lista, no existe.** No está
> escondido ni hay que activarlo: no existe. Esta regla ahorra horas.

Y ojo con algo que confunde a todo el mundo: **si preguntas por una métrica que no
existe, Prometheus no te dice que no existe.** Responde «Empty query result», que
es exactamente lo mismo que responde cuando el nombre es correcto pero no hay
datos. Es como preguntar en una tienda por un producto que no venden y que te
contesten «no queda».

<details>
<summary>La lista completa con descripciones, desde la terminal</summary>

```powershell
(Invoke-WebRequest -UseBasicParsing http://localhost:9187/metrics).Content -split "`n" | Select-String "^# HELP" | Select-Object -First 30
```

En Linux o Mac: `curl -s http://localhost:9187/metrics | grep "^# HELP" | head -30`

</details>

**Encuentra tú** la métrica que dice si el exporter puede hablar con Postgres.
*(Pista: es la más corta de todas y vale 1 o 0.)*

> **Por qué esa métrica es la primera que se mira siempre.** Es la que dice si
> puedes fiarte del resto: si vale 0, las otras 373 están congeladas en el último
> valor que se pudo leer, y siguen apareciendo en pantalla como si fueran
> actuales. Es el piloto de la nevera: no te dice si la comida está buena, te dice
> si la nevera está enchufada. Todos los exporters tienen la suya.

### Paso 10 — Las cuatro funciones que vas a usar todo el curso

Ejecuta estas una por una y mira la gráfica antes de pasar a la siguiente.

**`rate()` — velocidad de un contador**

```promql
rate(orderflow_orders_processed_total[5m])
```

Órdenes por segundo, promediadas sobre los últimos 5 minutos.

**Un contador es el cuentakilómetros de un coche: solo sube, nunca baja.** Si te
asomas y ves 48.320 km, ¿vas rápido o despacio? No tienes ni idea: ese número no
habla de ahora, habla de toda la vida del coche.

Lo que quieres es el **velocímetro**. Y el velocímetro no es más que mirar el
cuentakilómetros dos veces y dividir por el tiempo transcurrido. **`rate()` es el
velocímetro.**

> **El resultado sale con decimales**, algo como `0.7333`. Y no existen 0,73
> pedidos. Es como decir que vas a 80 km/h: no significa que en la próxima hora
> recorras 80 km exactos, es el ritmo al que vas ahora mismo. 0,73 pedidos por
> segundo son unos 44 por minuto.

**¿Y por qué `[5m]`?** Es cuánto tramo de carretera miras hacia atrás para
calcular la velocidad. Con `[10s]` el número da bandazos con cualquier bache; con
`[1h]` es tan suave que no te enteras de que te has parado. Cinco minutos es el
equilibrio habitual. Prueba a cambiarlo por `[1m]` y por `[30m]` y mira cómo la
misma gráfica se vuelve nerviosa o plana.

**`sum by ()` — agregar**

```promql
sum by (region) (rate(orderflow_orders_processed_total[5m]))
```

Lo mismo, pero una línea por región.

Fíjate en que `region` viene del código Python, mientras que en

```promql
sum by (service) (rate(orderflow_orders_processed_total[5m]))
```

la etiqueta `service` viene de `prometheus.yml` — la acabas de escribir tú en el
Paso 6. Prometheus las trata igual, pero se definen en sitios distintos.

**Compara los dos resultados.** La primera consulta te da 5 líneas, una por
región; la segunda, una sola. Suma las cinco de la primera con la calculadora:
**da exactamente el valor de la segunda**. No son dos datos distintos, es el
mismo dato partido de dos maneras. Como la factura de la luz, que puedes verla
como un total o desglosada por días: el consumo es el mismo, lo que cambia es por
dónde la cortas.

La segunda da una sola línea porque `service` solo tiene un valor posible aquí:
un único programa produce estos pedidos.

> ⚠️ **Cuidado: agrupar por una etiqueta que no existe también devuelve una sola
> línea**, y la pantalla se ve casi igual. La diferencia está en el resultado: en
> un caso pone `{service="processor"}` y en el otro `{}`, vacío.
>
> **Si te sale con las llaves vacías donde esperabas una etiqueta, has escrito
> mal el nombre de la etiqueta.**

Y de paso: **son cinco regiones** —lima, arequipa, trujillo, piura y cusco—. Si
en la Sesión 1 contaste cuatro, fue porque aquella consulta a la base de datos
traía solo los últimos cinco pedidos. **Una muestra no es un inventario.**

**`increase()` — total en una ventana**

```promql
increase(orderflow_orders_failed_total[10m])
```

Cuántas órdenes fallaron en los últimos 10 minutos, desglosadas por causa.

**`rate()` es el velocímetro; `increase()` es el cuentakilómetros parcial.** Uno
dice «vas a 80», el otro «has recorrido 12 km desde que salimos». Cuando alguien
de negocio pregunta «¿cuántos pedidos se nos han caído esta mañana?», no quiere
0,04 pedidos por segundo: quiere un número.

> **Aquí también salen decimales**, del tipo `46,8` fallos. Y no existen 0,8
> fallos. Prometheus mira el contador al principio y al final de la ventana, pero
> esas dos miradas no caen justo en el borde, así que estima lo que pasó en los
> huecos. **No es una cuenta exacta: es una estimación muy buena.**
>
> Para «¿tenemos un problema?» sirve perfectamente. Para «¿cuántos pedidos
> exactamente hay que reembolsar?», eso se le pregunta a la base de datos. **Un
> sistema de vigilancia sirve para detectar, no para contabilizar.**

**Solo verás cuatro causas, no diez.** El glosario `docs/metricas.md` lista diez
valores posibles, pero en un stack sano únicamente aparecen los cuatro fallos
simulados. Que veas cuatro es señal de que todo funciona.

Para quedarte solo con las tres causas principales:

```promql
topk(3, increase(orderflow_orders_failed_total[10m]))
```

> ⚠️ **`topk` no es información, es maquillaje.** Recorta la pantalla para que
> quepa. Ejecuta la consulta sin él y compara: es fácil que la tercera y la cuarta
> causa estén casi empatadas y `topk(3)` deje una fuera sin avisar.
>
> **La costumbre profesional:** mirar la consulta completa primero, y ponerle el
> `topk` solo después, para el panel. Si tomas una decisión mirando únicamente el
> top 3, estás decidiendo sobre datos que alguien recortó.

**`histogram_quantile()` — percentiles**

```promql
histogram_quantile(0.95, sum(rate(orderflow_processing_duration_seconds_bucket[5m])) by (le))
```

El P95 de la latencia: el valor por debajo del cual está el 95 % de las órdenes.

**Por qué hace falta esto y no basta un promedio.** Diez clientes entran en la
web. A nueve se les atiende en medio segundo. Al décimo se le queda la pantalla
colgada veinte segundos y se va. El tiempo medio de atención es de 2,45 segundos:
suena bien, nadie levanta una ceja en la reunión. **Pero el promedio se ha comido
al cliente que perdiste**, que era el único dato que importaba.

Ejecuta las tres versiones y compáralas:

```promql
histogram_quantile(0.50, sum(rate(orderflow_processing_duration_seconds_bucket[5m])) by (le))
```

```promql
rate(orderflow_processing_duration_seconds_sum[5m]) / rate(orderflow_processing_duration_seconds_count[5m])
```

El promedio y el P50 se parecerán mucho. El P95 será bastante mayor: **uno de
cada veinte pedidos tarda casi el doble**, y ese uno de cada veinte es una persona
esperando delante de una pantalla. Con 4.000 pedidos al día son doscientas
personas diarias con una mala experiencia, que el promedio no menciona ni una vez.

> **Nadie vive en el promedio.** Cada cliente vive su propia espera. El promedio
> es un número que no le ha pasado a nadie.

No hace falta entender la consulta por dentro: hay que saber copiarla.

> Tres cosas que fallan siempre aquí:
> 1. **El sufijo `_bucket`** es obligatorio. Sin él no hay percentil que calcular.
> 2. **`by (le)`** también. `le` es la etiqueta que marca cada corte del histograma.
> 3. **El prefijo `orderflow_`**. Sin él: "Empty query result".

> **El resultado sale como `{} 0.7875`, sin ninguna etiqueta, y es correcto.**
> Antes dijimos que unas llaves vacías suelen indicar un error, así que conviene
> aclararlo: para calcular el percentil hay que juntar todos los tramos en un solo
> montón —eso hace el `sum(...) by (le)`— y al juntarlo todo, las etiquetas se
> pierden por el camino. No queda ninguna que poner.
>
> La regla afinada: **llaves vacías donde esperabas una etiqueta = error; llaves
> vacías en un percentil = normal.**

### Paso 11 — Una pregunta de negocio, no de infraestructura

Éste es el patrón más valioso de PromQL: **dividir dos métricas para obtener una tercera**.

```promql
100 * sum(rate(orderflow_orders_failed_total[5m]))
/ clamp_min(
    sum(rate(orderflow_orders_processed_total[5m]))
    + sum(rate(orderflow_orders_failed_total[5m])),
    1)
```

El porcentaje de error del pipeline. Debería rondar el 5 %, que es el valor de
`ERROR_RATE_PCT` en tu `.env`.

**Nadie mide el porcentaje de error.** No existe un contador de «porcentaje». Lo
que hay es un contador de fallos y otro de aciertos, y el porcentaje sale de
dividirlos. Igual que nadie mide tu velocidad media en un viaje: mides
kilómetros, mides horas, y divides.

> **Párate en el número que te sale.** Alguien escribió «5» en un archivo de
> configuración. Ese número viajó al programa, el programa falló a ese ritmo, el
> fallo se contó, el contador se publicó, Prometheus lo recogió, y tú lo has
> recuperado por el otro extremo haciendo una división. **Toda la cadena
> funciona**, y lo sabes porque el número que sale por el final es el mismo que
> pusiste por el principio.
>
> Si sale 5,2 o 4,8 en vez de 5,0 exacto, es normal: estás midiendo una ventana
> de cinco minutos de un proceso que falla al azar. La realidad tiene decimales.

### La parte rara: `clamp_min(..., 1)`

Imagina que son las cuatro de la mañana y no entra ni un pedido. Cero bien, cero
mal. Y ahora preguntas: ¿qué porcentaje ha fallado? **Cero dividido entre cero.**
Esa pregunta no tiene respuesta, ni aquí ni en matemáticas, y la máquina responde
`NaN`, que significa «esto no es un número».

¿Y qué pasa en la Sesión 5, cuando le digas «avísame si el porcentaje supera el
10 %»? Que «esto no es un número» tampoco es menor que 10, y **la alarma suena. A
las cuatro de la mañana. Porque no pasaba nada.**

`clamp_min(algo, 1)` significa «si eso sale menor que 1, trátalo como 1». Es
poner un suelo. Nunca dividimos entre cero y no perdemos nada, porque con tráfico
normal el total es muchísimo mayor que 1.

> **La mayoría de las falsas alarmas de un sistema real no son fallos del
> sistema: son preguntas mal formuladas como ésta.** Alguien monta una alerta un
> viernes y un mes después nadie se cree ninguna alerta, porque suenan todas de
> madrugada sin motivo.

**Guarda esta consulta entera**, con el `clamp_min` incluido. Se reutiliza tal
cual en la Sesión 5.

---

## Bloque 3 — Pushgateway

### Paso 12 — El problema

Prometheus scrapea cada 15 segundos. Un script de ETL que arranca, trabaja 3
segundos y termina, nunca coincide con un scrape. Su métrica se pierde.

El Pushgateway es un buzón: el script **empuja** su métrica antes de morir, y el
buzón la conserva para que Prometheus la recoja cuando pase.

### Paso 13 — Dejar una nota en el buzón

En **PowerShell**, desde la carpeta del repositorio:

```powershell
Invoke-WebRequest -UseBasicParsing -Method POST -Uri http://localhost:9091/metrics/job/etl_nocturno -Body "orderflow_etl_registros_procesados 1500`n"
```

Debe responder `StatusCode : 200`.

Cómo se lee ese comando, trozo a trozo:

| Trozo | Qué significa |
|---|---|
| `-Method POST` | «Vengo a **dejar** algo», no a recoger |
| `.../metrics/job/etl_nocturno` | El remitente: **quién** deja la nota |
| `-Body "..."` | El contenido: `nombre_del_dato valor` |
| `` `n `` al final | Un salto de línea. **Es obligatorio** |

> **Ese `` `n `` es acento invertido + n**, la forma que tiene PowerShell de
> escribir «aquí va un salto de línea». El buzón **rechaza la nota sin él**, con
> un error que no explica nada. En un teclado español el acento invertido está
> arriba a la izquierda, junto al `1`.
>
> Y si te sale la advertencia de seguridad preguntando si continuar, es que falta
> `-UseBasicParsing`. **La respuesta por defecto es «No»**: si pulsas Enter sin
> leer, la métrica nunca llega y el ejercicio entero parece roto.

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
echo "orderflow_etl_registros_procesados 1500" | curl --data-binary @- http://localhost:9091/metrics/job/etl_nocturno
```

</details>

Espera 15 segundos —literalmente, el vigilante tiene que pasar— y consulta en
Prometheus:

```promql
orderflow_etl_registros_procesados
```

**Qué debes ver:** el valor 1500, con la etiqueta `job="etl_nocturno"`.

Esa etiqueta `job` es la que puso tu comando, no Prometheus. Funciona porque el
scrape config que escribiste lleva `honor_labels: true`. Sin esa línea,
Prometheus la habría pisado con `job="pushgateway"` y no sabrías qué script la
generó.

### Paso 14 — El peligro del Pushgateway

Vuelve a consultar la métrica dentro de un minuto. **Sigue valiendo 1500.**

El Pushgateway **nunca olvida**. Si tu ETL deja de ejecutarse, la métrica se
queda congelada en su último valor para siempre, y un panel que la muestre dirá
que todo va bien mientras el proceso lleva tres días muerto.

Imagínalo: el programa de madrugada deja su nota el lunes —«procesados 1500, todo
bien»—. El martes se rompe y no llega a ejecutarse. El miércoles tampoco. El
jueves tampoco. **El vigilante sigue pasando cada 15 segundos y sigue leyendo la
misma nota del lunes**, y tu panel sigue en verde. Llevas tres días sin procesar
nada y el sistema de vigilancia te dice que todo va bien.

> **Todo lo demás del curso te avisa cuando algo se para, porque deja de llegar
> información. El Pushgateway hace justo lo contrario: cuando algo se para, se
> queda repitiendo la última buena noticia.**

Por eso el Pushgateway se usa **solo** para jobs de corta duración, nunca para
servicios permanentes. Para borrarla:

```powershell
Invoke-WebRequest -UseBasicParsing -Method DELETE -Uri http://localhost:9091/metrics/job/etl_nocturno
```

<details>
<summary>La misma orden en Linux o Mac</summary>

```bash
curl -X DELETE http://localhost:9091/metrics/job/etl_nocturno
```

</details>

> En un sistema real nadie borra a mano. Se monta una alerta que vigila **cuánto
> tiempo hace que llegó la última nota** y salta si pasa demasiado. Se hace en la
> Sesión 5.

---

## Bloque 4 — Tu primera métrica en Python

Hasta ahora has *configurado* métricas que ya existían. Ahora vas a *crear* una.

### Paso 15 — El problema

Todas las métricas del stack miden infraestructura: cuántas órdenes, cuánto
tardan, cuántas fallan. **Ninguna mide dinero.** Si mañana un bug hiciera que
todas las órdenes se procesaran con importe cero, tu monitoreo diría que todo
funciona perfectamente.

Vamos a arreglarlo.

### Paso 16 — Escribir la métrica

Abre `services/order-processor/processor.py` en VS Code. Hay que tocar **dos
sitios distintos del mismo archivo**. Busca `TODO (Sesion 2)` con `Ctrl+F`: hay
dos.

Si quieres intentarlo por tu cuenta antes de mirar el código, la forma a copiar
es la de `orders_processed`, que está justo encima del primer TODO.

#### Pieza 1 — Crear el contador

Busca la línea que dice:

```python
# TODO (Sesion 2): declara aqui el Counter orderflow_order_amount_soles_total
```

Pon el cursor al final de esa línea, pulsa Enter, y escribe:

```python
order_amount = Counter(
    "orderflow_order_amount_soles_total",
    "Importe acumulado de las ordenes procesadas, en soles",
    ["region"],
)
```

Qué hace cada línea:

| Línea | Qué significa |
|---|---|
| `order_amount =` | El apodo con el que lo llamarás dentro del programa |
| `Counter(` | «Esto es un contador: un número que solo sube» |
| `"orderflow_order_amount..."` | El nombre **público**, el que se ve desde Prometheus |
| `"Importe acumulado..."` | La descripción, para que otro humano sepa qué es |
| `["region"]` | «Este contador va separado por regiones» |

> **Hay dos nombres y eso despista.** `order_amount` es como lo llamas tú dentro
> del archivo; `orderflow_order_amount_soles_total` es como lo ve el mundo. Como
> una persona a la que en casa llaman por el apodo y en el DNI le pone el nombre
> completo.

⚠️ `order_amount` debe quedar **pegado al margen izquierdo**, sin espacios
delante, igual que el `orders_processed = Counter(` de unas líneas más arriba.

#### Pieza 2 — Sumarle el dinero de cada pedido

Busca el segundo TODO. Ese trozo se ve así:

```python
            orders_processed.labels(region=region).inc()

            # TODO (Sesion 2): incrementa aqui tu Counter de importe.
            # El monto de la orden esta en order["total_amount"].
            # Recuerda que .inc() acepta un argumento numerico.
```

Pon el cursor al final de la última línea de comentario, pulsa Enter, y escribe:

```python
            order_amount.labels(region=region).inc(order["total_amount"])
```

⚠️ **Ésta sí lleva espacios delante: son 12.** En Python la sangría no es
estética, es sintaxis: si queda mal, el programa ni arranca. Tiene que quedar
**alineada exactamente** con la línea `orders_processed.labels(...)` que ves unas
líneas más arriba. Pon el cursor al principio de una y luego de la otra: el
número de columna que sale abajo a la derecha en VS Code debe ser el mismo.

Cómo se lee esa línea:

```
order_amount  .labels(region=region)  .inc(order["total_amount"])
     │                  │                        │
     │                  │                        └─ súmale este dinero
     │                  └─ en la casilla de esta región
     └─ al contador de importes
```

> **`.labels(...)` es la parte que se olvida todo el mundo.** Tu contador no es un
> número: es una hoja con cinco casillas, una por región. Antes de sumar tienes
> que decir **en qué casilla**. Si escribes `order_amount.inc(...)` a secas, el
> programa se estrella con un error que menciona «labels» — y ahora ya sabes qué
> significa: intentaste apuntar en la hoja sin elegir casilla.

#### Lo que NO debes hacer

**No añadas una etiqueta con el cliente.** Parece buena idea («así sé cuánto gasta
cada uno») y es la forma más común de reventar un sistema de vigilancia en
producción.

Cada valor distinto de una etiqueta crea una fila nueva en la memoria de
Prometheus, y esa fila ya no desaparece. Con la región tienes 5 filas. Con el
cliente tendrías una por cada persona que compre: diez mil clientes, diez mil
filas, de una sola medida. Eso no ralentiza Prometheus, **lo tumba**.

> **La regla: una etiqueta solo vale si sus valores posibles caben en una lista
> corta que puedas escribir de memoria.** Región: cinco. Motivo de error: diez.
> Cliente: no.

### Paso 17 — Reconstruir

Antes de nada, comprueba que el navegador **todavía no ve tu métrica**: abre
`http://localhost:8001/metrics` y busca `order_amount`. No está.

**Tu programa no se ejecuta desde el archivo que acabas de editar.** Cuando
montamos el stack, Docker cogió tu código y **le hizo una fotocopia**, que metió
en una caja cerrada. El programa que lleva horas funcionando trabaja con esa
fotocopia, y la fotocopia es de antes. Has corregido la receta en tu cuaderno,
pero el cocinero sigue con la fotocopia vieja pegada en la pared.

En **PowerShell**, desde la carpeta del repositorio, la línea completa:

```powershell
docker compose up -d --build order-processor
```

| Trozo | Qué significa |
|---|---|
| `up -d` | El de siempre: «pon esto en marcha» |
| `--build` | **«Antes de nada, haz una fotocopia nueva»** |
| `order-processor` | «Solo éste. Los otros doce no los toques» |

**Qué debes ver:** Docker reconstruye solo ese servicio. Los otros 12 ni se
enteran: la base de datos no se reinicia, la cola no pierde nada, Prometheus no
deja de vigilar ni un segundo. Eso es lo que se gana partiendo un sistema en
piezas.

> **Si aparece la palabra `CACHED` varias veces, es buena señal:** Docker está
> reutilizando el trabajo que ya tenía hecho (instalar las librerías, sobre todo).
> Reutilizar no es saltarse. Por eso a veces tarda 2 segundos y no 30.

> **Y el aviso que ahorra una hora:** si tu métrica nueva no aparece, la primera
> pregunta no es «¿qué escribí mal?», sino **«¿reconstruí la fotocopia?»**. Nueve
> de cada diez veces es eso.

### Paso 18 — Verificar

Abre `http://localhost:8001/metrics` en el navegador y busca `order_amount` con
`Ctrl+F`.

**Qué debes ver:** las líneas `# HELP`, `# TYPE` y un valor por cada región.

> Si no aparece nada, espera 20 segundos y recarga. **La serie no existe hasta que
> se procesa el primer pedido**: un contador con casillas por región no tiene la
> casilla de Lima hasta que llega el primer pedido de Lima.

> ⚠️ **Junto a tu métrica va a aparecer otra terminada en `_created`:**
>
> ```
> orderflow_order_amount_soles_total     ← la tuya
> orderflow_order_amount_soles_created   ← una impostora
> ```
>
> **No la escribiste tú: la genera la librería automáticamente**, y tiene la
> misma descripción exacta que la buena, así que en el autocompletado de
> Prometheus son indistinguibles por el texto. Lo que guarda es **la hora en que
> arrancó el contador**, no dinero.
>
> La buena es siempre la que termina en `_total`. Si alguna consulta te devuelve
> un número de diez cifras (algo como `1.787e+09`), casi seguro has cogido una
> fecha por error.

Espera un ciclo de scrape y, en Prometheus:

```promql
rate(orderflow_order_amount_soles_total[5m])
```

Ingresos por segundo. Y ahora el remate:

```promql
rate(orderflow_order_amount_soles_total[5m])
/
rate(orderflow_orders_processed_total[5m])
```

**El ticket promedio de los últimos 5 minutos.** Dos métricas que escribiste tú,
divididas entre sí, produciendo un indicador de negocio que ninguna de las dos
contenía por separado.

---

## Ejercicios (haz estos tú solo)

### Ejercicio A — Salud de la infraestructura

Encuentra y ejecuta las métricas que responden:

1. ¿Cuántas conexiones activas tiene Postgres ahora mismo?
2. ¿Cuánta memoria está usando Redis, en bytes?
3. ¿Cuántas claves hay en la base de datos de Redis?

*No te doy los nombres. Búscalos con el autocompletado de Prometheus escribiendo
`pg_` y `redis_`. Aprender a encontrar métricas es parte del ejercicio.*

Tres avisos para que no te atasques:

- **No busques el nombre exacto que tienes en la cabeza; busca un trozo.** Casi
  nunca se llama como uno esperaría. Prueba con `connections`, `backends`,
  `memory`, `keys`.
- **En la primera te van a salir varias filas**, una por base de datos
  (`template0`, `template1`, `postgres`, `orderflow_dw`). La que te interesa es
  `orderflow_dw`; las demás son bases internas de Postgres. Un exporter no filtra
  por ti: te lo da todo y tú eliges.
- **En la segunda el valor sale en notación científica**, algo como `1.33e+06`.
  Significa 1,33 por un millón: 1.330.000 bytes, o sea 1,3 megas. Los sistemas de
  vigilancia siempre dan bytes, nunca megas, porque «mega» significa cosas
  distintas según a quién preguntes.

Y una advertencia sobre la tercera: **el resultado que salga es correcto aunque no
lo parezca.** Párate a pensar por qué antes de dar por hecho que te has
equivocado. Dos pistas: Redis viene con dieciséis cajones numerados y nosotros
solo usamos uno; y «clave» no es lo mismo que «pedido» — una cola entera es una
sola clave, aunque tenga cien pedidos dentro, igual que una caja es un objeto
tenga lo que tenga dentro.

### Ejercicio B — La región más rentable

Escribe una consulta que devuelva el **ticket promedio por región** (no el global).

*Pista: la respuesta del Paso 18, pero con `sum by (region)` en el numerador y en
el denominador.*

Los dos fallos que se cometen aquí:

- **Poner `sum by (region)` solo arriba.** El resultado sale **vacío, sin ningún
  error**: estarías dividiendo algo que tiene una etiqueta entre algo que tiene
  cinco, y Prometheus no sabe emparejarlas. **Las dos partes de una división
  tienen que estar cortadas igual.**
- **Coger `orderflow_order_amount_soles_created` en lugar de `..._total`.** Es la
  impostora del Paso 18: guarda una fecha, no dinero. Sale un número de diez
  cifras y un ticket promedio absurdo.

> Los valores cambian cada vez que ejecutas la consulta, porque la ventana de 5
> minutos se va moviendo. Que no te cuadre con el de al lado es normal.

### Ejercicio C — Cardinalidad

Ejecuta esto y anota el número:

```promql
count({__name__=~"orderflow_.*"})
```

Ahora responde en dos líneas: si añadiéramos la etiqueta `order_id` a
`orderflow_orders_processed_total`, y el sistema procesa 1 orden por segundo,
¿cuántas series temporales tendríamos al cabo de un día? ¿Es viable?

---

## Si algo falla

| Síntoma | Causa probable | Solución |
|---|---|---|
| `docker compose config` da error de sintaxis | Indentación del YAML que pegaste | Servicios con 2 espacios, propiedades con 4, listas con 6 |
| `docker compose ps` muestra 10, no 13 | El bloque quedó fuera de `services:` | Comprueba que lo pegaste al final del archivo, después de `kibana` |
| `postgres-exporter` en rojo en Targets | Credenciales o Postgres aún arrancando | `docker compose logs postgres-exporter --tail 20` |
| Los 3 targets nuevos no aparecen | Prometheus no releyó su configuración | `docker compose restart prometheus` |
| "Empty query result" | Falta el prefijo `orderflow_` | Consulta `docs/metricas.md` |
| `histogram_quantile` devuelve `NaN` | Falta `_bucket` o falta `by (le)` | Revisa el Paso 10 |
| Tu métrica nueva no aparece | No reconstruiste la imagen | `docker compose up -d --build order-processor` |
| `curl` no funciona en Windows | En PowerShell es otro comando | Usa `Invoke-WebRequest` o el navegador |
| `El término 'head' no se reconoce` | `head`, `grep`, `tail` y `wc` son comandos de Linux | `head -20` → `Select-Object -First 20`; `grep x` → `Select-String x` |
| «Advertencia de seguridad: riesgo de ejecución de script» | Falta `-UseBasicParsing` | Añádelo. **Ojo: la respuesta por defecto es No** |
| `additional properties ... not allowed` | El bloque quedó pegado al margen al copiarlo de Word | Selecciónalo entero y pulsa `Tab` |
| `docker compose` dice que no encuentra configuración | Estás en otra carpeta | `cd` a la carpeta del repositorio |
| Tu métrica sale con un número de diez cifras | Cogiste la métrica `_created` | Usa la que termina en `_total` |
| El ticket promedio por región sale vacío | Falta `sum by (region)` en el denominador | Las dos partes de la división se cortan igual |

---

## Antes de la Sesión 3

1. **Baja el stack:** `docker compose down` (sin `-v`).
2. **Descarga de la plataforma** el archivo `orderflow.conf` de la Sesión 3. Lo
   necesitarás nada más empezar.
3. **Completa el entregable** con la plantilla `scripts/entregable_template.md`.

> En la Sesión 3 los logs dejan de ser texto que pasa por la pantalla y se
> convierten en datos que se pueden consultar. Kibana deja de estar vacío.
