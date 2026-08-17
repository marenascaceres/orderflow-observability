# OrderFlow — Observability Stack

Repositorio de práctica del curso **"Monitoreo y Registro con Python"** de BSG Institute.

Este proyecto simula el pipeline de datos de una empresa ficticia de e-commerce (**OrderFlow**) y trae el punto de partida sobre el que construirás, durante seis sesiones, un stack de observabilidad completo: métricas con Prometheus, logs con ELK, dashboards con Grafana y Kibana, y alertas con Alertmanager.

Todo corre en contenedores Docker en tu equipo local.

---

## Cómo funciona este repositorio

**Lo clonas una sola vez.** No hay que volver a descargar nada durante el curso.

Lo que hay aquí es el **punto de partida**: 10 servicios funcionando. A partir de la Sesión 2, cada sesión lo hace crecer, y **ese crecimiento lo escribes tú** en tu copia local, siguiendo el manual de la sesión.

| Al terminar la sesión | Servicios | Qué añades tú |
|:---:|:---:|---|
| 1 | 10 | Nada. Verificas y exploras |
| 2 | 13 | `postgres-exporter`, `redis-exporter`, `pushgateway` y tu primera métrica en Python |
| 3 | 13 | El segundo origen de logs y el pipeline que los estructura |
| 4 | 13 | El provisioning de Grafana y tu dashboard |
| 5 | 15 | `mailhog`, `webhook-receiver`, las reglas y el enrutamiento de alertas |
| 6 | 15 | Los notebooks que consultan todo desde Python |

> **Tu repositorio y el del docente van a divergir, y eso es lo correcto.** El
> tuyo crece con tu trabajo. Nunca hace falta un `git pull`.

Los archivos que no se teclean en clase —código Python largo, notebooks, pipelines de 120 líneas— **te los entrega el docente por la plataforma del curso**, unos días antes de cada sesión. El manual te dice dónde colocarlos.

---

## Requisitos

- **Docker Desktop** (Windows/Mac) o **Docker Engine + Compose** (Linux) — versión >= 24
- **RAM libre**: 6 GB mínimo (recomendado 8 GB)
- **Disco libre**: 10 GB (para imágenes + datos)
- **Python 3.11+** (para los validadores y, en la Sesión 6, los notebooks)

**Puertos libres.** Los diez primeros hacen falta desde la Sesión 1; el resto se van usando conforme el stack crece:

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
# 1. Clonar el repositorio (una sola vez en todo el curso)
git clone https://github.com/marenascaceres/orderflow-observability.git
cd orderflow-observability

# 2. Copiar variables de entorno
cp .env.example .env

# 3. Levantar todos los servicios (primera vez descarga ~2 GB)
docker compose up -d

# 4. Verificar estado
docker compose ps

# 5. Ejecutar el validador automático
python scripts/validate_setup.py
```

Después de ~1 minuto, los 10 servicios deben estar `Up` o `healthy`.

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

Y los que construirás más adelante:

| Servicio | URL | Desde |
|---|---|:---:|
| postgres-exporter | http://localhost:9187/metrics | Sesión 2 |
| redis-exporter | http://localhost:9121/metrics | Sesión 2 |
| Pushgateway | http://localhost:9091 | Sesión 2 |
| MailHog (buzón de prueba) | http://localhost:8025 | Sesión 5 |
| webhook-receiver | http://localhost:5001/health | Sesión 5 |

---

## Las tres cajas vacías

Al levantar el stack por primera vez arrancan 10 servicios, pero **tres están deliberadamente vacíos**:

| Servicio | Hoy | Se llena en |
|---|---|:---:|
| **Kibana** | Sin ningún Data View | Sesión 3 |
| **Grafana** | Con los datos conectados, sin un solo panel | Sesión 4 |
| **Alertmanager** | Corriendo, sin ninguna regla que le llegue | Sesión 5 |

No están rotos. Están esperándote.

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
├── docker-compose.yml       # Los 10 servicios del punto de partida
├── .env.example             # Plantilla de variables de entorno
├── README.md                # Este archivo
│
├── services/
│   ├── order-generator/     # Genera órdenes sintéticas
│   └── order-processor/     # Consume, valida, persiste e instrumenta
│                            # Trae el TODO del ejercicio de la Sesión 2
│
├── prometheus/              # Scraping (prometheus.yml) y reglas (alerts.yml)
├── alertmanager/            # Configuración base, se completa en la Sesión 5
├── logstash/                # Pipeline de ingesta de logs
├── grafana/provisioning/    # Datasources y dashboards por archivo
├── postgres/                # Init SQL del data warehouse
│
├── docs/
│   ├── metricas.md          # GLOSARIO CANÓNICO. La fuente de verdad
│   ├── sesion_01.md … 06.md # Los seis manuales de práctica
│   ├── mini_proyecto.md     # El encargo final
│   ├── prometheus_intro.md  # Lectura previa a la Sesión 2
│   ├── logstash_intro.md    # Lectura previa a la Sesión 4
│   ├── alertas_intro.md     # Lectura previa a la Sesión 5
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

## Comandos útiles

```bash
docker compose up -d              # Levantar todo
docker compose down               # Detener y eliminar contenedores
docker compose down -v            # Detener y BORRAR VOLÚMENES (reset total)
docker compose ps                 # Estado de servicios
docker compose config --services  # Comprobar el YAML sin levantar nada
docker compose logs <servicio>    # Logs de un servicio
docker compose logs -f <servicio> # Logs en tiempo real (Ctrl+C para salir)
docker compose restart <servicio> # Reiniciar un servicio
docker compose up -d --build      # Reconstruir imágenes locales
```

---

## Soporte

- **Errores comunes**: consulta [docs/troubleshooting.md](docs/troubleshooting.md).
- **Dudas del curso**: canal habilitado por el docente.

---

## Licencia

Material educativo. Uso interno para alumnos del curso.
