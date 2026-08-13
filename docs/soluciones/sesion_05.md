# Solución — Sesión 5

## Ejercicio B: la regla `SinOrdenesProcesadas`

Va al final de `prometheus/alerts.yml`, dentro del grupo
`orderflow_procesamiento`, en lugar del bloque `TODO`:

```yaml
      - alert: SinOrdenesProcesadas
        expr: sum(rate(orderflow_orders_processed_total[10m])) == 0
        for: 10m
        labels:
          severity: warning
          service: order-processor
        annotations:
          summary: "No se estan procesando ordenes"
          description: >-
            El order-processor no ha procesado ninguna orden en los ultimos
            10 minutos. Revisa la cola de Redis y los logs del processor.
```

Recarga y comprueba:

```bash
curl -X POST http://localhost:9090/-/reload
```

---

## Por qué `== 0` y no `< 1`

Son equivalentes aquí, pero `== 0` dice exactamente lo que quieres decir:
*ninguna*. Una regla se lee más veces de las que se escribe, muchas de ellas a
las tres de la mañana por alguien que no la escribió. Que diga lo que significa
importa.

## Por qué la ventana y el `for` valen los dos 10 minutos

No es redundante, aunque lo parezca.

`rate(...[10m])` mira los últimos 10 minutos y vale 0 solo si en toda esa ventana
no se procesó nada. `for: 10m` exige que esa condición se mantenga otros 10
minutos seguidos.

En la práctica eso significa que el sistema tiene que llevar unos 20 minutos
parado antes de que suene. Es a propósito: un atasco de dos minutos se resuelve
solo, y no merece despertar a nadie. Si tu negocio no tolera 20 minutos de
parada, baja los dos valores — pero bájalos entendiendo lo que ganas y lo que
pagas en falsos positivos.

## El detalle que hay que ver al pararlo

Al ejecutar `docker compose stop order-processor` disparas **dos** alertas del
mismo servicio:

| Alerta | Severidad | Cuándo |
|---|---|---|
| `ProcessorCaido` | critical | al minuto |
| `SinOrdenesProcesadas` | warning | a los ~20 minutos |

En `http://localhost:9090/alerts` verás las dos en `firing`. En Alertmanager solo
se notifica una.

Eso lo hace la regla de inhibición: cuando hay una `critical` activa, las
`warning` del **mismo** `service` se silencian. Y tiene sentido: el processor no
procesa órdenes *porque* está caído. Avisar de las dos cosas es contar el mismo
incidente dos veces.

Esa es la diferencia práctica entre detectar y notificar. Prometheus no deja de
detectar nunca; Alertmanager decide qué merece interrumpir a una persona.

---

## Ejercicio A: leer el payload

```bash
curl -s http://localhost:9093/api/v2/alerts
```

Cada elemento tiene un campo `receivers` con el destino que le tocó, y
`status.state` con `active`, `suppressed` o `unprocessed`.

Si tienes una alerta inhibida, aparecerá como `suppressed` con el campo
`status.inhibitedBy` apuntando al identificador de la crítica que la silenció.
Es la prueba, en datos, de lo que explica el apartado anterior.
