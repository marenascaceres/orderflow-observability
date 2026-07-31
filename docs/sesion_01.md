# Sesión 1 — Fundamentos de monitoreo y levantamiento del stack

**Duración:** 2 horas
**Modalidad:** sincrónica online
**Capítulo 1:** Observabilidad y captura de datos operativos

---

## Objetivos de aprendizaje

Al terminar esta sesión, serás capaz de:

1. Explicar los tres pilares de la observabilidad y la diferencia entre monitoreo y observabilidad.
2. Identificar qué hace cada componente del stack (Prometheus, Alertmanager, ELK, Grafana).
3. Usar comandos básicos de Docker y `docker compose` para levantar, inspeccionar y detener servicios.
4. Levantar el stack completo de **OrderFlow** en tu equipo y verificar que los 10 servicios respondan.
5. Describir el caso OrderFlow y qué se monitorea en cada etapa del pipeline.

---

## Antes de la sesión

- Instalar Docker Desktop siguiendo la guía asincrónica entregada por el docente.
- Verificar que `docker --version` y `docker compose version` funcionan.
- Tener este repositorio clonado (o al menos la URL a mano).

---

## Los 3 pilares de la observabilidad

| Pilar        | Responde                     | Herramienta en este curso |
|--------------|------------------------------|---------------------------|
| **Métricas** | ¿QUÉ está pasando?           | Prometheus + Grafana      |
| **Logs**     | ¿POR QUÉ está pasando?       | Logstash + Elasticsearch + Kibana |
| **Trazas**   | ¿DÓNDE exactamente ocurrió?  | (no cubierto en este curso) |

---

## El caso OrderFlow

Simulamos el pipeline de datos de una empresa de e-commerce. El **generator** produce órdenes sintéticas, las encola en **Redis**, el **processor** las consume, valida, procesa y persiste en **Postgres** (data warehouse).

**KPIs del negocio que monitorearemos:**
- **Throughput**: órdenes/segundo
- **Latencia**: P50, P95, P99 del procesamiento
- **Tasa de error**: % de órdenes fallidas

---

## Los 6 comandos de Docker que necesitas

```bash
docker compose up -d              # levantar todos los servicios
docker compose down               # detener y eliminar
docker compose ps                 # estado de servicios
docker compose logs <servicio>    # ver logs
docker compose logs -f <servicio> # logs en tiempo real
docker compose restart <servicio> # reiniciar un servicio
```

---

## Práctica guiada — 40 minutos

### Paso 1 — Verificar Docker

```bash
docker --version
docker compose version
```

### Paso 2 — Clonar el repo (si no lo hiciste antes)

```bash
git clone https://github.com/marenascaceres/orderflow-observability.git
cd orderflow-observability
```

### Paso 3 — Recorrido por la estructura del repo

Abrir en VS Code:

```bash
code .
```

Explorar:
- `docker-compose.yml` — los 10 servicios definidos
- `services/order-generator/` y `services/order-processor/` — código Python
- `prometheus/prometheus.yml` — configuración de scraping
- `logstash/pipeline/orderflow.conf` — pipeline de ingesta de logs
- `grafana/provisioning/` — datasources precargados

### Paso 4 — Copiar variables de entorno

```bash
cp .env.example .env
```

En Windows PowerShell: `Copy-Item .env.example .env`

### Paso 5 — Levantar el stack

```bash
docker compose up -d
```

La primera vez descarga ~2 GB en imágenes. Puede tomar entre 5 y 10 minutos según la conexión.

### Paso 6 — Verificar salud de los servicios

```bash
docker compose ps
```

Todos deben aparecer con estado `Up` o `healthy`. Elasticsearch puede tomar 30-60 segundos adicionales.

### Paso 7 — Verificar cada servicio (checklist)

| # | Servicio        | URL o comando                                          | Qué debes ver                        |
|:-:|-----------------|--------------------------------------------------------|--------------------------------------|
| 1 | Prometheus      | http://localhost:9090                                  | UI con menú Status → Targets         |
| 2 | Alertmanager    | http://localhost:9093                                  | Lista de alertas (vacía)             |
| 3 | Grafana         | http://localhost:3000                                  | Login (admin/admin)                  |
| 4 | Elasticsearch   | http://localhost:9200                                  | JSON con `"cluster_name"`            |
| 5 | Kibana          | http://localhost:5601                                  | Pantalla de bienvenida               |
| 6 | order-generator | http://localhost:8000/metrics                          | Métricas en texto plano              |
| 7 | order-processor | http://localhost:8001/metrics                          | Métricas en texto plano              |
| 8 | Postgres        | `docker compose exec postgres pg_isready -U orderflow` | `accepting connections`              |
| 9 | Redis           | `docker compose exec redis redis-cli ping`             | `PONG`                               |
|10 | Logstash        | `docker compose logs logstash \| tail`                 | Pipeline iniciado                    |

**Atajo:** puedes correr el validador automático:

```bash
python3 scripts/validate_setup.py
```

---

## Práctica exploratoria — 20 minutos

### Ejercicio A — Ver el pipeline funcionando

```bash
docker compose logs -f order-generator
```

Deberías ver mensajes tipo:
```
2026-07-31 03:12:15 INFO - Order generated: id=8c4a2f9b, region=lima, items=3, total=S/127.50
```

`Ctrl+C` para salir del stream (no detiene el servicio).

Ahora el processor:
```bash
docker compose logs -f order-processor
```

Verás eventos **JSON estructurados** tipo:
```json
{"timestamp":"2026-07-31T03:12:15Z","level":"INFO","event":"order_processed","order_id":"8c4a2f9b-...","region":"lima","total_amount":127.50}
```

> Nota la diferencia: el generator emite logs de texto plano, el processor emite JSON estructurado. En Sesión 3 vamos a ver por qué el JSON es superior para análisis.

### Ejercicio B — Primera métrica en Prometheus

1. Abrir http://localhost:9090
2. Ir a **Status → Targets** y verificar que `order-generator` y `order-processor` están en verde (**UP**).
3. Ir a **Graph**, escribir `orderflow_orders_processed_total` y hacer click en **Execute**.
4. Click en la pestaña **Graph** — verás una línea creciendo.

### Ejercicio C — Primeros logs en Kibana

1. Abrir http://localhost:5601
2. Menú lateral → **Discover**
3. Crear un **Data View**:
   - Name: `orderflow-logs`
   - Index pattern: `orderflow-logs-*`
   - Timestamp field: `@timestamp`
4. Guardar. Volverás a Discover con los logs apareciendo en tiempo real.

> Si no ves logs: verifica en el selector de tiempo (arriba a la derecha) que el rango sea "Last 15 minutes" y refresca.

---

## Entregable

Al finalizar la sesión, sube al LMS un archivo `entregable_sesion1.md` (puedes usar la plantilla de `scripts/entregable_sesion1_template.md`) que contenga:

1. Screenshot de `docker compose ps` con los 10 servicios en `Up`/`healthy`.
2. Tabla completada con: servicio, URL/comando, estado verificado, y qué rol cumple en OrderFlow.
3. Respuesta breve (2-4 líneas): *¿Por qué necesitamos métricas Y logs en el mismo pipeline, y no solo uno de los dos?*

**Rúbrica:**
- Screenshot correcto — 40 pts
- Tabla completa y correcta — 40 pts
- Reflexión propia y coherente — 20 pts

---

## Tarea previa a la Sesión 2

1. **Bajar el stack** para liberar RAM:
   ```bash
   docker compose down
   ```
2. **Leer** [docs/prometheus_intro.md](prometheus_intro.md) — 10 minutos de lectura.
3. **Subir el entregable** al LMS antes de que empiece la Sesión 2.
