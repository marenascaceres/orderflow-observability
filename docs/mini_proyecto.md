# Mini proyecto — Observabilidad de un servicio nuevo

## El encargo

OrderFlow va a incorporar un servicio nuevo: **`order-shipper`**, encargado de
despachar las órdenes que el `order-processor` ya validó y guardó.

Nadie lo ha instrumentado. Tu trabajo es dejarlo observable: que se pueda ver
cómo va, que quede rastro de lo que hace, que avise si se rompe, y que se pueda
consultar desde código.

No tienes que escribir el servicio. Tienes que hacer visible lo que hace.

---

## Qué construir

Trabajas sobre tu propio clon del repositorio, sobre el stack de 15 servicios que
ya tienes funcionando. Todo lo que añadas debe convivir con lo que ya está: nada
de reemplazar configuración existente.

### 1. El servicio

Crea `services/order-shipper/` a imagen y semejanza del `order-processor`. Puede
ser deliberadamente simple: lee órdenes de una cola o de Postgres, simula un
despacho con una latencia variable, y falla de vez en cuando.

Lo importante no es la lógica de negocio. Es todo lo demás.

### 2. Métricas

Instrumenta al menos **cuatro** métricas con `prometheus_client`, y que entre
ellas haya como mínimo un `Counter`, un `Gauge` y un `Histogram`.

Todas con el prefijo `orderflow_`, y documentadas en `docs/metricas.md` siguiendo
el formato que ya tiene ese archivo: nombre, tipo, etiquetas, qué mide.

Piensa las etiquetas antes de escribirlas. Vas a tener que justificar por qué
elegiste esas y no otras.

### 3. Logs

Que el servicio emita logs estructurados y lleguen a Elasticsearch por el
pipeline que ya existe. Elige tú si por TCP en JSON, como el processor, o por el
driver syslog, como el generator — pero explica por qué elegiste ese camino.

Los logs deben incluir al menos un campo de alta cardinalidad (un identificador)
que **no** esté en las métricas.

### 4. Un scrape job

Añade el servicio a `prometheus/prometheus.yml`, con las mismas etiquetas
`service` y `component` que llevan los demás.

### 5. Dashboard

Añade a `grafana/dashboards/orderflow-overview.json` una fila con tus paneles, o
crea un dashboard propio en la misma carpeta. Debe quedar provisionado desde
archivo: si borras el dashboard desde la interfaz, tiene que volver.

### 6. Al menos dos alertas

En `prometheus/alerts.yml`, con `for`, `severity`, `service` y anotaciones
legibles. Una de las dos debe ser `critical` y la otra `warning`, del mismo
servicio, para que la inhibición tenga algo que hacer.

Tienen que **dispararse de verdad**. Provoca el fallo y compruébalo.

### 7. Un informe en Python

Un notebook o un script que consulte tus métricas y tus logs, y produzca un
veredicto sobre la salud de `order-shipper`, con los mismos umbrales que usan tus
alertas y tus paneles.

---

## Qué entregar

Un solo repositorio (tu clon, con tus commits) y un documento breve que responda a
estas preguntas:

1. **Las métricas.** Por qué elegiste esos cuatro tipos y esas etiquetas. Qué
   etiqueta te tentó añadir y descartaste, y por qué.

2. **Los logs.** Por qué TCP o por qué syslog. Qué campo de alta cardinalidad
   metiste en los logs y no en las métricas, y qué habría pasado si lo hubieras
   metido en las métricas.

3. **Las alertas.** De dónde salen tus umbrales. Qué pasaría si el `for` fuera
   diez veces más corto.

4. **Una consulta que optimizaste.** La versión ingenua, la versión buena, y el
   número de series de cada una.

5. **Una captura de cada cosa funcionando:** los paneles con datos, la alerta en
   `firing`, la notificación recibida, y la salida de tu informe.

Los commits importan. Deben ser aditivos, como los del curso: cada uno añade algo
que funciona, ninguno rompe lo anterior. Un `git log` legible dice más de tu
trabajo que cualquier documento.

---

## Cómo se mira

No se mira que funcione. Eso es el mínimo.

Se mira el **criterio**: que las etiquetas estén elegidas y no puestas, que los
umbrales tengan una razón detrás, que el dashboard responda preguntas en vez de
mostrar gráficos, y que las alertas sean accionables. Una alerta que suena tres
veces por semana y que nadie atiende es peor que no tenerla.

Se mira también la **coherencia**: que el panel, la alerta y el informe midan lo
mismo con los mismos números. Si el gráfico dice una cosa y el correo otra, el
equipo deja de creer a los dos.

---

## Punto de partida

Todo lo que necesitas ya lo hiciste una vez a lo largo del curso:

| Parte | Dónde lo hiciste |
|---|---|
| Instrumentar en Python | Sesión 2, Bloque 4 |
| Un scrape job nuevo | Sesión 2, Bloque 1 |
| Logs hasta Elasticsearch | Sesión 3, Bloques 2 y 3 |
| Dashboard provisionado | Sesión 4, Bloque 4 |
| Reglas y enrutamiento | Sesión 5, Bloques 1 y 2 |
| Consultar desde Python | Sesión 6, Bloques 1 y 4 |

Y los nombres de todo están en `docs/metricas.md`.
