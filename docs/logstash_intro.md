# Introducción a Logstash — lectura previa a Sesión 4

Esta lectura repasa lo que vimos en Sesión 3. Si te la perdiste, este documento alcanza para seguir Sesión 4 sin problema.

## 1. ¿Qué problema resuelve Logstash?

Prometheus (Sesión 2) responde "¿cuánto? ¿cuándo?" a través de métricas agregadas. Los logs responden "¿qué pasó exactamente, y por qué?" — el detalle de un evento puntual, con contexto (`order_id`, `reason`, mensaje).

**Arquitectura ELK:**

- **Elasticsearch** — guarda e indexa los documentos (los logs ya transformados).
- **Logstash** — recolecta, transforma y envía.
- **Kibana** — interfaz para explorar y buscar sobre lo que hay en Elasticsearch.

Grafana también puede consultar Elasticsearch (su datasource ya está provisionado en este repo apuntando a `orderflow-logs-*`) — eso lo usamos recién en Sesión 4.

## 2. Anatomía de un pipeline

Un archivo `.conf` de Logstash tiene tres bloques:

```
input { ... }   # de dónde vienen los datos
filter { ... }  # transforma el evento crudo en campos
output { ... }  # a dónde va el evento transformado
```

### Input

Define el origen de los datos. En este curso usamos dos:

- `tcp` con `codec => json_lines` — recibe conexiones TCP donde cada línea es un evento JSON completo. Así manda sus logs `order-processor`.
- `syslog` — recibe mensajes en formato syslog, típicamente por UDP. Así manda sus logs `order-generator`, vía el driver de logging `syslog` de Docker.

### Filter

Transforma el evento crudo en campos estructurados. Los filtros más comunes:

- **`json` / `json_lines` (codec de input, no filter):** cuando el log ya es JSON válido, no hace falta filtro adicional para parsearlo — Logstash lo interpreta directamente.
- **`grok`:** cuando el log es texto libre sin estructura fija. Usa patrones con nombre (`%{TIPO:nombre_campo}`) para extraer valores mediante expresiones regulares con nombre. Es más frágil que `json`: si el formato del log cambia, el patrón deja de matchear.
- **`date`:** convierte un campo de fecha del propio log en el `@timestamp` del evento. Sin esto, Elasticsearch usaría la hora en que el documento fue *indexado*, no la hora en que el evento realmente *ocurrió*.
- **`mutate`:** conversiones de tipo, agregar/quitar campos, agregar tags.

Ejemplo de patrón grok, sobre un log de texto plano:

```
Log real:
2026-07-31 14:32:07,481 INFO - Order generated: id=a1b2c3d4, region=lima, items=3, total=S/145.90

Patrón:
"Order generated: id=%{DATA:order_id_short}, region=%{WORD:region}, items=%{NUMBER:items_count:int}, total=S/%{NUMBER:total_amount:float}"
```

Cada `%{TIPO:nombre}` extrae un pedazo del texto y lo guarda como campo con ese nombre. `TIPO` es un patrón predefinido (`WORD`, `NUMBER`, `DATA`, `IP`, `TIMESTAMP_ISO8601`, etc.); `:int` o `:float` al final fuerza el tipo de dato del campo resultante.

**Cómo depurar un grok que no matchea:** si el patrón no coincide con el mensaje, Logstash no descarta el evento — lo indexa igual, pero le agrega el tag `_grokparsefailure`. Ese tag es la primera señal a revisar cuando un campo no aparece como esperabas.

### Output

A dónde va el evento ya transformado. En este curso:

```
output {
  elasticsearch {
    hosts => ["http://elasticsearch:9200"]
    index => "orderflow-logs-%{+YYYY.MM.dd}"
    action => "create"
  }
}
```

- El índice incluye la fecha (`%{+YYYY.MM.dd}`) para no acumular todo en un único índice gigante — facilita borrar o retener datos por antigüedad sin afectar otros días.
- `action => "create"` evita que un evento sobreescriba un documento existente con el mismo `_id`.

## 3. Consultas básicas en Elasticsearch

Por API REST, sin pasar por Kibana:

```bash
# Listar índices y cuántos documentos tiene cada uno
curl -s "localhost:9200/_cat/indices?v"

# Buscar documentos por campo
curl -s "localhost:9200/orderflow-logs-*/_search?q=level:ERROR&pretty"
curl -s "localhost:9200/orderflow-logs-*/_search?q=event:order_failed&pretty"
```

En Kibana (`localhost:5601`), la vía equivalente es **Discover**, sobre el index pattern `orderflow-logs-*` con time field `@timestamp`.

## 4. Extender un pipeline sin romperlo

Cuando agregás una fuente de datos nueva a un pipeline que ya funciona:

1. Agregá el `input` nuevo sin tocar el existente.
2. Usá `tags` en cada input para poder distinguir el origen de cada evento dentro del `filter`.
3. Envolvé la lógica de `filter` específica de cada origen en un condicional (`if "tag" in [tags] { ... }`), en vez de reescribir todo.
4. Mantené un único `output` si querés que todo caiga al mismo índice — útil para consultar y armar dashboards sobre todas las fuentes juntas.

## 5. Qué viene en Sesión 4

Con métricas (Prometheus) y logs (Elasticsearch, vía este pipeline) ya capturados, Sesión 4 construye dashboards operativos en Grafana y Kibana sobre estos mismos datos — sin volver a tocar la ingesta.
