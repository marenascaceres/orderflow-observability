# Manual de práctica — Sesión 6

## Optimización e integración con Python

**Capítulo 2:** Dashboards, alertas e integración aplicada

> Las diapositivas explican la teoría; los comandos y las consultas salen de aquí.
> Si una consulta de la pantalla no coincide con este documento, manda este documento.

---

## Qué vas a construir hoy

Hoy **dejas de mirar por pantalla**.

Grafana y Kibana son excelentes para observar. Pero un informe que se genera solo
cada mañana, un chequeo que corre en cada despliegue, o una notificación con tu
propio criterio, no se hacen con clics: se hacen con código.

El stack no crece: siguen siendo 15 servicios. Lo que cambia es quién los
consulta. Hasta hoy, tú a través de un navegador. Desde hoy, Python.

Al terminar serás capaz de:

- Consultar la API HTTP de Prometheus con `query` y `query_range`.
- Leer y agregar logs de Elasticsearch con el cliente oficial de Python.
- Razonar el coste de una consulta y reducirlo con `sum by` y recording rules.
- Construir un informe de salud que combine métricas, logs y un veredicto.

---

## Punto de partida

Necesitas los **cinco archivos** que descargaste de la plataforma: los cuatro
notebooks `.ipynb` y su `requirements.txt`.

**Paso 1.** Crea la carpeta `notebooks/` en tu repositorio y copia dentro los
cinco archivos:

**Windows (PowerShell):**
```powershell
New-Item -ItemType Directory -Force -Path notebooks
Copy-Item "$HOME\Downloads\*.ipynb","$HOME\Downloads\requirements.txt" notebooks\
```

**Mac/Linux:**
```bash
mkdir -p notebooks
cp ~/Downloads/*.ipynb ~/Downloads/requirements.txt notebooks/
```

Comprueba que están los cinco:

```bash
ls notebooks
```

> **Cuidado con `requirements.txt`.** Ya existen otros dos en tu repositorio, uno
> por cada servicio Python. Éste es distinto y va en `notebooks/`. Si lo copias
> encima de `services/order-processor/requirements.txt`, rompes el processor.

**Paso 2.** Levanta el stack y comprueba que `ERROR_RATE_PCT` está en `5`:

```bash
docker compose up -d
```

Si lo dejaste en 30 al final de la Sesión 5, los números de hoy van a salir en
rojo desde el principio y el informe final perderá gracia.

**Paso 3.** Instala las dependencias. Estas van en **tu** máquina, no en un
contenedor: los notebooks consultan el stack desde fuera, por `localhost`, igual
que lo haría un script en tu trabajo.

```bash
pip install -r notebooks/requirements.txt
```

**Paso 4.** Arranca JupyterLab:

```bash
jupyter lab
```

Se abre el navegador. Entra en la carpeta `notebooks/`.

---

## Dónde se escribe cada cosa

Este manual mezcla varios sitios distintos. Antes de empezar, ten claro cuál es cuál:

| Si el bloque empieza por… | Va en… |
|---|---|
| `docker`, `Invoke-WebRequest` | **PowerShell**, siempre desde la carpeta del repositorio |
| `rate(`, `sum(`, `increase(`, `count(` | **El navegador**, en `http://localhost:9090` → pestaña **Graph** |
| Texto con sangría (YAML, Python) | **VS Code**, en el archivo que se indique |
| `http://localhost:...` a secas | **El navegador** |

**Todos los comandos de Docker de este curso se escriben desde la carpeta del
repositorio.** Tu PowerShell debe mostrar algo así antes del cursor:

```
PS D:\...\orderflow-observability>
```

Si no es así, colócate ahí antes de nada:

```powershell
cd C:\ruta\donde\clonaste\orderflow-observability
```

`docker compose` no adivina qué stack quieres manejar: busca el archivo
`docker-compose.yml` **en la carpeta donde estás parado**. Desde otro sitio te
dirá que no encuentra ninguna configuración.

> **Y si un comando te responde «no se reconoce el término X»**, no está roto tu
> ordenador: ese comando es de otro idioma. `head`, `tail`, `grep` y `wc` son de
> Linux y Mac. En Windows PowerShell se dice así:
>
> | Quiero… | Linux / Mac | Windows PowerShell |
> |---|---|---|
> | Ver solo el principio | `head -20` | `Select-Object -First 20` |
> | Ver solo el final | `tail -20` | `Select-Object -Last 20` |
> | Buscar una palabra | `grep queue` | `Select-String queue` |
> | Contar líneas | `wc -l` | `Measure-Object -Line` |

---

## Bloque 1 — La API de Prometheus

Abre `01_prometheus_api.ipynb`.

**Paso 5.** Ejecuta la primera celda de código (`Shift + Enter`).

Define `prom_query()` y lanza `sum(orderflow_orders_processed_total)`. Debe
devolver una lista con un elemento, y dentro un par `[timestamp, "valor"]`.

Fíjate en un detalle que sorprende a todo el mundo la primera vez: **el valor
viene como cadena de texto**, no como número. La API lo devuelve así a propósito,
para no perder precisión en números muy grandes. Si vas a operar con él, hay que
convertirlo con `float()`.

**Paso 6.** Ejecuta la celda de la función `existe()`.

Compara dos nombres: `orderflow_orders_processed_total` y
`orders_processed_total`. El segundo devuelve `NO EXISTE`.

> **Este es el error más caro de la sesión y merece un minuto.** Cuando consultas
> una métrica que no existe, Prometheus **no da error**. Devuelve una lista
> vacía, exactamente igual que si existiera pero no tuviera datos. La consulta
> parece bien escrita y el resultado parece "todavía no hay tráfico".
>
> Se pierden tardes enteras así. La función `existe()` es tres líneas y te ahorra
> todas.

**Paso 7.** Ejecuta el resto del notebook: la consulta de rango y la gráfica.

`query_range` necesita `start`, `end` y `step`. Ese `step` es la distancia entre
puntos: con `15s` sobre una hora salen 240 puntos. Pedir `step=1s` sobre una
semana devolvería 600.000 puntos por serie y tumbaría la petición. El `step` no
es un detalle cosmético: es el coste de la consulta.

---

## Bloque 2 — Los logs desde Python

Abre `02_elasticsearch_logs.ipynb`.

**Paso 8.** Ejecuta la conexión y la búsqueda de errores.

Fíjate en `level.keyword`. Elasticsearch indexa cada campo de texto **dos veces**:
como `text`, troceado en palabras para poder buscar dentro; y como `keyword`, el
valor entero, para filtrar y agrupar de forma exacta.

Un `term` sobre `level` puede no devolver nada, porque compara el valor exacto
contra un campo que fue troceado. Sobre `level.keyword` funciona siempre. Es la
misma razón por la que Kibana te ofrece `reason.keyword` cuando quieres agrupar.

**Paso 9.** Ejecuta la agregación por nivel, y después la de `tags`.

La primera cuenta sin traerse un solo documento: `size=0`. Por la red viaja un
resumen de tres líneas en vez de mil documentos. Es la diferencia entre un script
que tarda 200 ms y uno que tarda 30 segundos.

La segunda te muestra los dos orígenes por separado: `processor` y `generator`.
Ese campo `tags` lo pusiste tú en el pipeline de Logstash de la Sesión 3, en los
`input`. Lo que estás consultando hoy es consecuencia directa de aquel archivo.

**Paso 10.** Ejecuta la celda de pandas.

---

## Bloque 3 — Lo que cuesta una consulta

Abre `03_optimizacion_promql_kql.ipynb`.

**Paso 11.** Ejecuta la celda que compara el número de series con `n_series()`.

Sin agregar, obtienes una serie por región. Agregando con `sum by (service)`,
una sola. En un dashboard que se refresca cada 10 segundos, esa diferencia se
multiplica por 8.640 al día.

**Paso 12.** Ejecuta la celda de `series_totales()`.

Es la cuenta que hay que saber hacer **antes** de añadir una etiqueta: el número
de series es el producto de los valores posibles de todas las etiquetas.

Mira el último número, el que incluye `order_id`. Es la respuesta cuantificada al
Ejercicio C de la Sesión 2. Cada una de esas series ocupa memoria en Prometheus
de forma permanente, aunque reciba un solo dato.

La regla práctica: una etiqueta vale si sus valores son **pocos, conocidos y
estables**. `region` sí. `customer_id` no. `order_id`, jamás.

Y lo que necesita cardinalidad alta —el identificador de una orden concreta— va
en los **logs**. Por eso el `order_id` está en Elasticsearch y no en Prometheus.
Los dos pilares no compiten: se reparten el trabajo según el coste.

**Paso 13.** Lee el apartado de recording rules.

Una recording rule calcula la expresión cara cada 30 segundos y guarda el
resultado como métrica nueva. El panel lee un número ya hecho.

---

## Bloque 4 — El informe de salud

Abre `04_practica_final.ipynb`.

**Paso 14.** Ejecuta las tres celdas en orden.

La última imprime un informe con throughput, porcentaje de error, latencia p95,
errores en los logs, y un veredicto: `OK`, `ATENCIÓN` o `CRÍTICO`.

**Paso 15.** Fíjate en los umbrales de la función `veredicto()`: error por encima
del 10 %, o p95 por encima de 1 segundo, es `CRÍTICO`.

Son **exactamente** los mismos números de la alerta de la Sesión 5 y del panel de
la Sesión 4. Eso no es una coincidencia ni una casualidad de diseño: es el punto
al que lleva el curso entero.

Cuando el dashboard, la alerta y el informe miden lo mismo con los mismos
umbrales, el equipo tiene **una** versión de la verdad. Cuando cada herramienta
usa su propio criterio, llega el día en que el gráfico está verde, el correo dice
que arde, y el informe de la mañana dice otra cosa. Y entonces nadie cree a
ninguno.

**Paso 16 — Verlo cambiar.** Sube `ERROR_RATE_PCT` a `30` en tu `.env`:

```bash
docker compose up -d order-processor
```

Espera unos minutos y vuelve a ejecutar las celdas 2 y 3. El veredicto cambia a
`CRÍTICO` sin que hayas tocado el código.

Devuélvelo a `5` cuando termines.

**Paso 17.** Ejecuta el validador:

```bash
python scripts/validate_sesion6.py
```

---

## Ejercicios (haz estos tú solo)

### Ejercicio A — Errores por hora

En `02_elasticsearch_logs.ipynb`, cuenta cuántos errores hubo **por hora** en las
últimas 6 horas, con una agregación `date_histogram` sobre `@timestamp`.

Después, agrupa las órdenes fallidas por su campo `reason` y compara el resultado
con lo que devuelve esta consulta en Prometheus:

```promql
topk(5, sum by (reason) (orderflow_orders_failed_total))
```

Los dos números salen de sistemas distintos y deberían contar la misma historia.
Explica en dos líneas cualquier diferencia que encuentres.

*Pista: los valores posibles de `reason` están en `docs/metricas.md`.*

### Ejercicio B — La recording rule

En `03_optimizacion_promql_kql.ipynb`, escribe completa la recording rule para el
p95 de latencia, con su nombre siguiendo la convención `nivel:metrica:operacion`,
y di qué panel de tu dashboard la usaría.

*Pista: la expresión ya la tienes en el panel 3 de la Sesión 4 y en la regla
`LatenciaAltaP95` de la Sesión 5.*

### Ejercicio C — Cerrar el ciclo

Amplía `04_practica_final.ipynb` para que:

1. Guarde el informe en `informe_salud.txt`, con fecha y hora.
2. Repita la medición cada minuto durante cinco minutos y muestre la evolución.
3. **Envíe el informe al `webhook-receiver` de la Sesión 5** cuando el veredicto
   sea `CRÍTICO`.

Con eso cierras el ciclo completo del curso: métricas y logs capturados,
consultados por código, evaluados con criterio propio, y convertidos en un aviso
que llega solo.

*El endpoint es `http://localhost:5001/alertas` y acepta un POST con JSON.
Compruébalo con `docker compose logs --tail 30 webhook-receiver`.*

---

## Si algo falla

| Síntoma | Causa probable | Solución |
|---|---|---|
| `ConnectionError` a `localhost:9090` | El stack no está levantado | `docker compose up -d` |
| Una consulta devuelve `[]` | El nombre de la métrica no existe | Úsalo con `existe()`, Paso 6 |
| `ApiError` del cliente de Elasticsearch | Versión del cliente distinta a la del servidor | `pip install "elasticsearch==8.13.*"` |
| El `term` sobre `level` no devuelve nada | Falta el sufijo `.keyword` | Paso 8 |
| `ModuleNotFoundError` | Faltan dependencias | `pip install -r notebooks/requirements.txt` |
| El veredicto sale `SIN DATOS` | El pipeline lleva poco tiempo | Deja correr 5 minutos |
| El p95 sale `None` | Falta `_bucket` o falta `sum by (le)` | Revisa la expresión |
| Jupyter no abre | El puerto 8888 está ocupado | `jupyter lab --port 8889` |

Para cualquier otro problema: `docs/troubleshooting.md`.

---

## Cierre del curso

Mira atrás un momento. En la Sesión 1 tenías tres pantallas vacías: Kibana,
Grafana y Alertmanager. Las tres están llenas, y las llenaste tú:

| Sesión | Qué añadiste |
|---|---|
| 1 | El stack en pie y la primera métrica leída con tus ojos |
| 2 | Exporters, PromQL y una métrica instrumentada por ti en Python |
| 3 | Dos orígenes de logs, estructurados y consultables |
| 4 | Un dashboard que vive como código y sobrevive a que borren el volumen |
| 5 | Alertas que avisan solas, con criterio de a quién y cuándo |
| 6 | Todo lo anterior, leído desde Python y convertido en una decisión |

El stack pasó de 10 a 15 servicios sin que nada dejara de funcionar por el camino.
Cada sesión añadió; ninguna reemplazó.

**El mini proyecto** está en `docs/mini_proyecto.md`.
