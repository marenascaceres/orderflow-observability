# OrderFlow — Observability Stack

Repositorio de práctica del curso **"Monitoreo y Registro con Python"** de BSG Institute.

Este proyecto simula el pipeline de datos de una empresa ficticia de e-commerce (**OrderFlow**) y expone toda la infraestructura de observabilidad necesaria para monitorearlo: métricas con Prometheus, logs con ELK, dashboards con Grafana y Kibana, y alertas con Alertmanager.

Todo corre en contenedores Docker en tu equipo local. **El stack crece durante el
curso**: arranca con 10 servicios en la Sesión 1 y termina con 15 en la Sesión 6.

Cada sesión añade capacidades sobre lo que ya funciona. Nunca se reemplaza
configuración ni se vuelve atrás: si algo funcionaba en la Sesión 2, sigue
funcionando en la 6.

| Al terminar la sesión | Servicios | Qué se añadió |
|:---:|:---:|---|
| 1 | 10 | El pipeline y las herramientas, tres de ellas vacías a propósito |
| 2 | 13 | `postgres-exporter`, `redis-exporter`, `pushgateway` |
| 3 | 13 | Los dos orígenes de logs llegando a Elasticsearch |
| 4 | 13 | Dashboards provisionados desde archivo |
| 5 | 15 | `mailhog`, `webhook-receiver` y las alertas |
| 6 | 15 | Los notebooks que consultan todo desde Python |

---

## Requisitos

- **Docker Desktop** (Windows/Mac) o **Docker Engine + Compose** (Linux) — versión >= 24
- **RAM libre**: 6 GB mínimo (recomendado 8 GB)
- **Disco libre**: 10 GB (para imágenes + datos)
- **Python 3.11+** (para los validadores y, en la Sesión 6, los notebooks)

**Puertos libres.** Los siete primeros hacen falta desde la Sesión 1; el resto se
van usando conforme el stack crece:

| Sesión | Puertos |
|:---:|---|
| 1 | 3000, 5044, 5432, 5601, 6379, 8000, 8001, 9090, 9093, 9200 |
| 2 | 9091 (pushgateway), 9121 (redis-exporter), 9187 (postgres-exporter) |
| 3 | 5000/udp (syslog de Logstash) |
| 5 | 1025 y 8025 (MailHog), 5001 (webhook-receiver) |

> **Guía de instalación paso a paso**: ver el PDF de instalación entregado por el docente antes de la primera sesión.

---

## Arranque rápido

```bash
# 1. Clonar el repositorio
git clone https://github.com/marenascaceres/orderflow-observability.git
cd orderflow-observability

# 2. Copiar variables de entorno
cp .env.example .env

# 3. Levantar todos los servicios (primera vez descarga ~2 GB)
docker compose up -d

# 4. Verificar estado
docker compose ps

# 5. (Opcional) Ejecutar el validador automático
python3 scripts/validate_setup.py
```

Después de ~1 minuto, todos los servicios deben estar `Up` o `healthy`.

---

## URLs de los servicios

| Servicio        | URL                              | Credenciales   |
|-----------------|----------------------------------|----------------|
| Prometheus      | http://localhost:9090            | -              |
| Alertmanager    | http://localhost:9093            | -              |
| Grafana         | http://localhost:3000            | admin / admin  |
| Kibana          | http://localhost:5601            | -              |
| Elasticsearch   | http://localhost:9200            | -              |
| order-generator | http://localhost:8000/metrics    | -              |
| order-processor | http://localhost:8001/metrics    | -              |

Y los que aparecen más adelante:

| Servicio | URL | Desde |
|---|---|:---:|
| postgres-exporter | http://localhost:9187/metrics | Sesión 2 |
| redis-exporter | http://localhost:9121/metrics | Sesión 2 |
| Pushgateway | http://localhost:9091 | Sesión 2 |
| MailHog (buzón de prueba) | http://localhost:8025 | Sesión 5 |
| webhook-receiver | http://localhost:5001/health | Sesión 5 |

---

## Arquitectura

```
   order-generator (Python)
           |
           v
        Redis (cola)
           |
           v
   order-processor (Python)  --------->  Postgres (DW)
           |            \
    (métricas)       (logs JSON)
           |               \
           v                v
      Prometheus         Logstash
       /      \             |
      v        v            v
Alertmanager  Grafana   Elasticsearch
                            |
                            v
                         Kibana
```

**Pipeline de datos**: el generator produce órdenes sintéticas, las encola en Redis, el processor las consume, valida, procesa y persiste en Postgres.

**Observabilidad**:
- El processor emite **métricas Prometheus** (contadores de órdenes procesadas/fallidas, histogramas de latencia) que Prometheus scrapea cada 15s.
- El processor emite **logs JSON estructurados** que envía por TCP a Logstash, que los parsea e indexa en Elasticsearch.
- Grafana y Kibana son las UIs de exploración; Alertmanager gestiona las notificaciones.

---

## Estructura del repositorio

```
orderflow-observability/
├── docker-compose.yml       # Definición de los servicios
├── .env.example             # Plantilla de variables de entorno
├── README.md                # Este archivo
│
├── services/
│   ├── order-generator/     # Genera órdenes sintéticas
│   ├── order-processor/     # Consume, valida, persiste e instrumenta
│   └── webhook-receiver/    # Recibe alertas de Alertmanager (Sesión 5)
│
├── prometheus/              # Scraping (prometheus.yml) y reglas (alerts.yml)
├── alertmanager/            # Enrutamiento e inhibición de alertas
├── logstash/                # Pipeline de ingesta de logs
├── grafana/
│   ├── provisioning/        # Datasources, dashboards y alertas por archivo
│   └── dashboards/          # Tus dashboards en JSON (Sesión 4)
├── postgres/                # Init SQL del data warehouse
│
├── notebooks/               # Los cuatro notebooks de la Sesión 6
│
├── docs/
│   ├── metricas.md          # GLOSARIO CANÓNICO. La fuente de verdad
│   ├── sesion_01.md … 06.md # Manuales de práctica
│   ├── soluciones/          # Se publican después de cada sesión
│   ├── mini_proyecto.md     # El encargo final
│   ├── prometheus_intro.md  # Lectura previa a la Sesión 2
│   ├── logstash_intro.md    # Lectura previa a la Sesión 3
│   ├── grafana_kibana_intro.md
│   └── troubleshooting.md   # Errores comunes y soluciones
│
└── scripts/
    ├── validate_setup.py    # Health-check del stack (Sesión 1)
    ├── validate_sesion2.py … validate_sesion6.py
    └── entregable_template.md
```

> **`docs/metricas.md` manda.** Si un nombre de métrica que ves en una
> diapositiva no coincide con el que hay ahí, el bueno es el del glosario. Todas
> las métricas propias llevan el prefijo `orderflow_`; las de los exporters
> llevan `pg_` o `redis_`.

---

## Progresión del curso por sesiones

| Sesión | Tema | Qué cambia en el repo |
|:------:|---|---|
| **1** | Fundamentos y levantamiento del stack | Se verifica lo que ya está; Kibana, Grafana y Alertmanager quedan vacíos a propósito |
| **2** | Métricas con Prometheus y exporters | +3 servicios, +3 scrape jobs, y tú instrumentas un `Counter` en `processor.py` |
| **3** | Logs con Logstash y Elasticsearch | Segundo origen de logs por syslog; grok estructura el texto plano |
| **4** | Visualización en Grafana y Kibana | Provisioning de dashboards; tu dashboard pasa a ser un archivo del repo |
| **5** | Alertas y notificaciones | +2 servicios; reglas, enrutamiento, inhibición y notificación real |
| **6** | Optimización e integración con Python | Los notebooks consultan Prometheus y Elasticsearch desde código |

Cada sesión tiene su tag en git. Para ver el repositorio tal como quedó al
terminar una sesión concreta:

```bash
git checkout sesion-3    # y para volver al final: git checkout main
```

---

## Comandos útiles

```bash
docker compose up -d              # Levantar todo
docker compose down               # Detener y eliminar contenedores
docker compose down -v            # Detener y BORRAR VOLÚMENES (reset total)
docker compose ps                 # Estado de servicios
docker compose logs <servicio>    # Logs de un servicio
docker compose logs -f <servicio> # Logs en tiempo real (Ctrl+C para salir)
docker compose restart <servicio> # Reiniciar un servicio
docker compose build              # Reconstruir imágenes locales (generator/processor)
```

---

## Soporte

- **Errores comunes**: consulta [docs/troubleshooting.md](docs/troubleshooting.md).
- **Dudas del curso**: canal habilitado por el docente.

---

## Licencia

Material educativo. Uso interno para alumnos del curso.
