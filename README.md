# OrderFlow — Observability Stack

Repositorio de práctica del curso **"Monitoreo y Registro con Python"** de BSG Institute.

Este proyecto simula el pipeline de datos de una empresa ficticia de e-commerce (**OrderFlow**) y expone toda la infraestructura de observabilidad necesaria para monitorearlo: métricas con Prometheus, logs con ELK, dashboards con Grafana y Kibana, y alertas con Alertmanager.

Todo corre en **10 contenedores Docker** en tu equipo local.

---

## Requisitos

- **Docker Desktop** (Windows/Mac) o **Docker Engine + Compose** (Linux) — versión >= 24
- **RAM libre**: 6 GB mínimo (recomendado 8 GB)
- **Disco libre**: 10 GB (para imágenes + datos)
- **Puertos libres**: 3000, 5044, 5432, 5601, 6379, 8000, 8001, 9090, 9093, 9200
- **Python 3.11+** (solo para ejecutar el script de validación; no necesario para el stack)

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
├── docker-compose.yml       # Definición de los 10 servicios
├── .env.example             # Plantilla de variables de entorno
├── README.md                # Este archivo
│
├── services/
│   ├── order-generator/     # Servicio Python que genera órdenes
│   └── order-processor/     # Servicio Python que procesa e instrumenta
│
├── prometheus/              # Config de scraping y reglas de alerta
├── alertmanager/            # Config de enrutamiento de alertas
├── logstash/                # Pipeline de ingesta de logs
├── grafana/                 # Provisioning de datasources y dashboards
├── postgres/                # Init SQL del data warehouse
│
├── docs/
│   ├── sesion_01.md         # Guía del alumno para Sesión 1
│   ├── prometheus_intro.md  # Lectura previa a Sesión 2
│   └── troubleshooting.md   # Errores comunes y soluciones
│
└── scripts/
    ├── validate_setup.py    # Health-check automático del stack
    └── entregable_sesion1_template.md
```

---

## Progresión del curso por sesiones

| Sesión | Tema                                         | Qué se agrega/modifica en el repo                       |
|:------:|----------------------------------------------|---------------------------------------------------------|
| **1**  | Fundamentos + levantamiento del stack        | (nada — solo se usa lo que ya está)                     |
| **2**  | Métricas con Prometheus y exporters          | Se explora `processor.py`; PromQL en `docs/`            |
| **3**  | Logs con Logstash y Elasticsearch            | Se editan filtros de `logstash/pipeline/`               |
| **4**  | Dashboards en Grafana y Kibana               | Se agregan JSONs en `grafana/dashboards/` y Kibana obj  |
| **5**  | Alertas con Alertmanager y Grafana           | Se completan `prometheus/alerts.yml` y `alertmanager/`  |
| **6**  | Optimización + integración Python            | Se agregan notebooks en `notebooks/`                    |

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
