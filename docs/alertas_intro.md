# Lectura previa a Sesión 5 — De dashboards a alertas

Esta lectura es corta (10-15 min) y da contexto para la Sesión 5: **Alertas y notificaciones
operativas**. No hace falta ejecutar nada todavía — es solo para llegar con la idea clara.

## De dónde venimos

En Sesión 4 armaste un dashboard de Grafana con 5 paneles: throughput, error rate, latencia P95,
queue depth e infraestructura (conexiones a Postgres). También armaste un dashboard de Kibana
con visualizaciones sobre los logs de OrderFlow.

Un dashboard es **pasivo**: alguien tiene que estar mirándolo para darse cuenta de que algo
anda mal. Eso funciona bien en una demo o en una revisión puntual, pero no escala — nadie
mira un dashboard 24/7.

## La pregunta que resuelve la Sesión 5

> ¿Cómo hacemos que el sistema nos avise a nosotros, en vez de que nosotros tengamos que
> ir a buscarlo?

Esa es la diferencia entre **observar** (dashboards) y **alertar** (notificaciones activas).

## Dos caminos distintos para alertar, ambos con Prometheus

### 1. Alertas en Grafana (alerting nativo)

Grafana puede evaluar una query periódicamente y, si cruza un umbral, disparar una alerta
desde el propio panel. Es el camino más directo: la misma query del panel de "Error rate %"
que armaste en Sesión 4 puede convertirse en una regla de alerta con un clic.

- Ventaja: todo vive en un solo lugar (la query, el panel y la alerta).
- Limitación: pensado para alertas ligadas a un dashboard específico.

### 2. Alertmanager (el componente dedicado del stack Prometheus)

Prometheus evalúa reglas definidas en `prometheus/alerts.yml` (hoy vacío — lo vas a completar
en Sesión 5) y, cuando una regla se cumple, envía la alerta a **Alertmanager**. Alertmanager
no evalúa nada — su trabajo es recibir alertas ya disparadas y decidir **qué hacer con ellas**:
agruparlas, silenciarlas, enrutarlas a distintos canales, evitar notificaciones duplicadas.

- Ventaja: pensado para alertas centralizadas de todo el stack, no solo de un dashboard.
- Es el camino que exige el sílabo del curso para esta sesión.

## El contraste que vamos a construir en Sesión 5

| | Alertas en Grafana | Alertmanager |
|---|---|---|
| Dónde vive la regla | En Grafana; en el curso, en un archivo que Grafana carga al arrancar | `prometheus/alerts.yml` |
| Quién evalúa | Grafana | Prometheus |
| Quién decide cómo notificar | Grafana (contact points) | Alertmanager (routes, receivers) |
| Bueno para | Alertas ligadas a un panel puntual | Alertas centralizadas de todo el sistema |

## Una pista de lo que viene

La consulta del panel "Tasa de error %" de la Sesión 4 no fue un ejercicio suelto: es
exactamente la que vas a reutilizar como condición de una regla de alerta real. El panel se
pone amarillo al 5 % y rojo al 15 %; la alerta avisará al pasar del 10 %, en plena zona
amarilla, para que te enteres antes de que llegue a rojo.

## Lo que necesitas traer a la Sesión 5

**Una cuenta de Gmail personal con la verificación en dos pasos activada.** Las alertas de
la sesión llegarán a tu correo de verdad, y Google solo permite que un programa envíe correo
con una *contraseña de aplicación*, que exige esa verificación. Actívala antes de clase: el
proceso incluye confirmar desde tu móvil y conviene no hacerlo con prisa.

Algunas cuentas de empresa o de centros educativos no permiten contraseñas de aplicación.
Si es tu caso, usa una cuenta personal.

## Para llegar con esto claro a Sesión 5

- ¿Qué diferencia hay entre que un panel se ponga rojo y que alguien reciba una notificación?
- ¿Por qué separar "quién evalúa la condición" de "quién decide cómo avisar" es útil en un
  equipo real, y no solo una complicación técnica?

No hace falta responder por escrito — es para llegar pensando en esto a la próxima clase.
