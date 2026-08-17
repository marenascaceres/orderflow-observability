# Troubleshooting

Guía de errores comunes al levantar y usar el stack. Ordenado por síntoma.

---

## Docker / arranque

### `docker: command not found`
Docker Desktop no está instalado o no está en el PATH. Reinstala siguiendo la guía asincrónica.

### `Cannot connect to the Docker daemon`
Docker Desktop no está corriendo. Abre Docker Desktop y espera a que el ícono de la ballena quede fijo (no animado).

### `pull access denied` o descarga muy lenta
- Verifica que Docker Desktop tenga acceso a internet.
- Si estás en una red corporativa con proxy, configura el proxy en Settings → Resources → Proxies.
- Reintenta: `docker compose up -d` retoma la descarga donde se quedó.

### `port is already allocated`
Otro proceso usa uno de los puertos del stack. Identifícalo:

- **Windows:** `netstat -ano | findstr :3000`
- **Mac/Linux:** `lsof -i :3000`

Detén el proceso o cambia el puerto en `.env` (por ejemplo `GRAFANA_PORT=3001`).

### `no space left on device`
Disco lleno. Necesitas al menos 10 GB libres. Libera espacio con:
```bash
docker system prune -a --volumes
```
⚠️ Esto borra imágenes, contenedores detenidos y volúmenes no usados.

---

## Servicios individuales

### Elasticsearch entra en `restarting` en loop

**Síntoma en logs:** `max virtual memory areas vm.max_map_count [65530] is too low`

**Solución (Linux/WSL2):**
```bash
sudo sysctl -w vm.max_map_count=262144
```
Para hacerlo permanente:
```bash
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

**En Docker Desktop (Mac/Windows):** este parámetro ya está configurado en la VM interna, así que este error no debería aparecer. Si aparece, actualiza Docker Desktop.

### Elasticsearch se queda en `starting` mucho tiempo

Es normal. Tarda 30-60 segundos en pasar a `healthy`. Si toma más de 3 minutos:
```bash
docker compose logs elasticsearch | tail -30
```
Busca errores relacionados con memoria. Si tu laptop tiene 8 GB, reduce el heap en `.env`:
```
ES_JAVA_OPTS=-Xms384m -Xmx384m
```

### Target `DOWN` en Prometheus

Uno de los servicios Python no arrancó bien.
```bash
docker compose logs order-generator
docker compose logs order-processor
```

Errores comunes:
- **No puede conectar a Redis:** verifica que Redis esté `healthy` con `docker compose ps`.
- **No puede conectar a Postgres:** lo mismo con Postgres.

Reinicia el servicio problemático:
```bash
docker compose restart order-processor
```

### Grafana: login `admin/admin` no funciona

Verifica en `.env` los valores de `GRAFANA_ADMIN_USER` y `GRAFANA_ADMIN_PASSWORD`. Si los cambiaste después de la primera corrida, tienes que resetear el volumen:
```bash
docker compose down
docker volume rm orderflow_grafana_data
docker compose up -d
```

### Kibana: `Kibana server is not ready yet`

Kibana tarda más que Elasticsearch en estar lista. Espera 60 segundos y refresca. Si persiste:
```bash
docker compose logs kibana | tail -20
```

### Kibana: `Discover` no muestra logs

Tres causas comunes:

1. **No creaste el Data View.** Menú → Stack Management → Data Views → Create. Index pattern: `orderflow-logs-*`, Timestamp field: `@timestamp`.
2. **Rango de tiempo incorrecto.** Arriba a la derecha, ajusta a "Last 15 minutes".
3. **Logstash aún no ingesta.** Verifica:
   ```bash
   docker compose logs logstash | tail
   curl http://localhost:9200/_cat/indices | grep orderflow
   ```
   Debe aparecer al menos un índice `orderflow-logs-YYYY.MM.dd`.

### El processor no envía logs a Logstash

Verifica que Logstash esté escuchando en 5044:
```bash
docker compose logs logstash | grep -i "starting.*5044"
```
Si no aparece, revisa `logstash/config/logstash.yml` y la pipeline en `logstash/pipeline/orderflow.conf`.

El processor tolera que Logstash no esté disponible (no bloquea el pipeline principal), así que si arrancó antes que Logstash, los primeros logs se pierden pero el resto sí llegan.

---

## Archivos que entrega el docente por la plataforma

Tres sesiones necesitan archivos que no vienen en el repositorio. El docente los
publica en la plataforma unos días antes. **Cada uno tiene su sitio exacto**: si
lo dejas en otra carpeta, no falla con un mensaje claro — simplemente no ocurre
nada.

| Antes de | Archivo | Dónde va |
|:---:|---|---|
| Sesión 3 | `orderflow.conf` | `logstash/pipeline/orderflow.conf` (reemplaza el que hay) |
| Sesión 5 | `app.py`, `Dockerfile`, `requirements.txt` | `services/webhook-receiver/` (carpeta nueva) |
| Sesión 5 | `orderflow-alerts.yml` | `grafana/provisioning/alerting/` (carpeta nueva) |
| Sesión 6 | 4 × `.ipynb` + `requirements.txt` | `notebooks/` (carpeta nueva) |

**Comprueba dónde estás antes de copiar.** Todas las rutas de la tabla son
relativas a la raíz del repositorio, la carpeta donde está `docker-compose.yml`.

```bash
ls docker-compose.yml
```

Si eso da error, no estás en la raíz y las rutas no funcionarán.

> **Ojo con los `requirements.txt`.** Hay tres distintos en el curso: uno del
> generator, uno del processor y el de los notebooks. Copiar uno encima de otro
> rompe el servicio afectado. El de la Sesión 6 va en `notebooks/`, en ninguna
> otra parte.

---

## Servicios que aparecen más adelante

Los de esta sección solo existen si ya hiciste la sesión que los añade. Si aún no
has llegado, que no aparezcan es lo correcto.

### El exporter de Postgres o de Redis está `DOWN` (Sesión 2)

Comprueba primero si el exporter responde de verdad:

```bash
curl -s http://localhost:9187/metrics | head -5     # postgres
curl -s http://localhost:9121/metrics | head -5     # redis
```

Si no responde, casi siempre es la contraseña: el `DATA_SOURCE_NAME` del
`postgres-exporter` se construye con las variables de tu `.env`. Si cambiaste
`POSTGRES_PASSWORD` después de la primera corrida, Postgres conserva la vieja
dentro del volumen y el exporter no entra.

```bash
docker compose logs postgres-exporter --tail 20
```

### La métrica de Postgres del dashboard sale vacía (Sesión 4)

Los nombres que expone un exporter dependen de su versión y de qué colectores
tenga activos. **No los des por sabidos: pregúntaselos.**

```bash
curl -s http://localhost:9187/metrics | grep "^# HELP pg_stat_database"
```

Usa el nombre que salga de ahí. Lo mismo con `redis_` en el puerto 9121.

### No llegan los logs del generator (Sesión 3)

El driver de logging de Docker se aplica al **crear** el contenedor, no al
reiniciarlo:

```bash
docker compose up -d --force-recreate order-generator
```

Y recuerda que ese driver corre en el demonio de Docker, **fuera** de la red de
Compose. Por eso apunta a `udp://localhost:5000` y no a `udp://logstash:5000`,
que es lo que uno escribiría por instinto.

### Aparece `_grokparsefailure` o `_dateparsefailure` (Sesión 3)

Ninguno de los dos hace fallar nada: el documento entra en Elasticsearch igual,
pero mal. Por eso hay que buscarlos a propósito.

```bash
curl -s "http://localhost:9200/orderflow-logs-*/_count?q=tags:_grokparsefailure"
curl -s "http://localhost:9200/orderflow-logs-*/_count?q=tags:_dateparsefailure"
```

- **grok**: el patrón no casa con el texto. Compara el patrón con una línea real.
- **date**: el formato de fecha no está contemplado. El processor emite
  `2026-08-12 03:12:15,842` — separador espacio y coma decimal, que **no** es
  ISO8601 estricto. Si el filtro `date` solo declara `ISO8601`, falla en silencio
  y los logs aparecen desplazados unos segundos.

### Los paneles dicen `Datasource not found` (Sesión 4)

El dashboard busca el datasource por su `uid`. Comprueba que los tuyos lo tengan
fijado:

```bash
docker compose up -d --force-recreate grafana
```

Si sigue, mira que `grafana/provisioning/datasources/datasources.yml` tenga
`uid: prometheus` y `uid: elasticsearch`.

### No aparece la carpeta `OrderFlow` en Dashboards (Sesión 4)

El provider relee la carpeta cada 30 segundos, así que espera antes de dudar. Si
pasado ese tiempo no aparece, suele ser un error de sintaxis en el JSON:

```bash
docker compose logs grafana --tail 30 | grep -i error
```

### Una alerta nunca sale de `Inactive` (Sesión 5)

Una regla con un nombre de métrica inexistente **no da error**: simplemente no
dispara nunca. Es la peor forma de fallar que puede tener una alerta.

Copia la `expr` de la regla, pégala en la pestaña **Graph** de Prometheus y mira
si devuelve algo. Si devuelve vacío, el problema está en el nombre. Compáralo con
`docs/metricas.md`.

Recuerda también que la alerta tarda: `rate([5m])` más `for: 2m` suman varios
minutos reales antes del disparo.

### La alerta llega al webhook pero no al correo (Sesión 5)

Es el fallo silencioso clásico de Alertmanager. Si la última ruta lleva
`matchers: severity=~"warning|info"`, una alerta `critical` no casa con ninguna
ruta hermana después de la primera y nunca llega al correo.

La ruta final debe ir **sin matchers**, para que recoja todo lo que llegue hasta
ella.

### MailHog vacío (Sesión 5)

```bash
curl -X POST http://localhost:9093/-/reload
docker compose logs alertmanager --tail 20
```

Un `dial tcp: connection refused` significa que MailHog aún estaba arrancando.
Espera 30 segundos.

### Los notebooks no encuentran las librerías (Sesión 6)

```bash
pip install -r notebooks/requirements.txt
```

Si el cliente de Elasticsearch da `ApiError` o se queja de la versión, es que no
coincide la serie mayor con la del servidor. El compose levanta Elasticsearch 8.x,
así que el cliente tiene que ser 8.x.

### Una consulta desde Python devuelve `[]` (Sesión 6)

Prometheus **no da error** cuando la métrica no existe: devuelve una lista vacía,
igual que si existiera y no tuviera datos. Compruébalo:

```bash
curl -s http://localhost:9090/api/v1/label/__name__/values | grep orderflow
```

El notebook 1 trae una función `existe()` para esto mismo.

---

## Rendimiento

### El laptop se pone lento con el stack corriendo

El stack completo consume ~4-5 GB de RAM (más al final del curso, cuando son 15
servicios). Recomendaciones:

- Cierra apps innecesarias (Chrome con 50 pestañas, Slack, Teams).
- Baja el heap de Elasticsearch en `.env` a 384m:
  ```
  ES_JAVA_OPTS=-Xms384m -Xmx384m
  LS_JAVA_OPTS=-Xms192m -Xmx192m
  ```
- Detén el stack cuando no lo uses: `docker compose down`.

### Prometheus consume mucho disco

Prometheus retiene métricas 15 días por defecto. Para reducir, agrega en el `command` del servicio en `docker-compose.yml`:
```yaml
- '--storage.tsdb.retention.time=3d'
```

---

## Reset completo del stack

Si algo está muy roto y quieres empezar desde cero:

```bash
# Detiene todo y BORRA los volúmenes (perderás datos de Postgres, ES, Grafana)
docker compose down -v

# Elimina imágenes locales del generator y processor
docker image rm orderflow-order-generator orderflow-order-processor 2>/dev/null

# Vuelve a levantar (reconstruye imágenes y descarga imágenes base)
docker compose up -d --build
```

---

## No encuentras tu error aquí

1. Ejecuta el validador para ubicar el problema:
   ```bash
   python3 scripts/validate_setup.py
   ```
2. Revisa logs del servicio afectado:
   ```bash
   docker compose logs <servicio> --tail 100
   ```
3. Consulta al docente por el canal de soporte del curso.
