# Entregable — Sesión 1: Fundamentos y levantamiento del stack

**Alumno/a:** _(tu nombre)_
**Fecha:** _(YYYY-MM-DD)_

---

## 1. Screenshot: `docker compose ps` con los 10 servicios corriendo

_(Pega aquí el screenshot mostrando los 10 servicios en estado `Up` o `healthy`. Si tu LMS no soporta imágenes en Markdown, sube el screenshot como archivo aparte)_

![docker compose ps](./docker-compose-ps.png)

---

## 2. Tabla de servicios verificados

| # | Servicio        | URL o comando                                      | Verificado | Rol en OrderFlow                                 |
|---|-----------------|----------------------------------------------------|:----------:|--------------------------------------------------|
| 1 | Prometheus      | http://localhost:9090                              | ☐          | _(completar)_                                    |
| 2 | Alertmanager    | http://localhost:9093                              | ☐          | _(completar)_                                    |
| 3 | Grafana         | http://localhost:3000                              | ☐          | _(completar)_                                    |
| 4 | Elasticsearch   | http://localhost:9200                              | ☐          | _(completar)_                                    |
| 5 | Kibana          | http://localhost:5601                              | ☐          | _(completar)_                                    |
| 6 | order-generator | http://localhost:8000/metrics                      | ☐          | _(completar)_                                    |
| 7 | order-processor | http://localhost:8001/metrics                      | ☐          | _(completar)_                                    |
| 8 | Postgres        | `docker compose exec postgres pg_isready -U orderflow` | ☐      | _(completar)_                                    |
| 9 | Redis           | `docker compose exec redis redis-cli ping`         | ☐          | _(completar)_                                    |
|10 | Logstash        | `docker compose logs logstash \| tail`             | ☐          | _(completar)_                                    |

_(Marcar la columna "Verificado" con ✅ y completar el rol de cada servicio en una frase.)_

---

## 3. Reflexión

**Pregunta:** ¿Por qué necesitamos métricas Y logs en el mismo pipeline, y no solo uno de los dos?

_(Escribe tu respuesta en 2 a 4 líneas, con tus palabras.)_
