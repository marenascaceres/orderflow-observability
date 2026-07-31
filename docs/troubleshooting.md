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

## Rendimiento

### El laptop se pone lento con el stack corriendo

10 servicios consumen ~4-5 GB de RAM. Recomendaciones:

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
