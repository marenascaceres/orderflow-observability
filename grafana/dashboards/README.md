# grafana/dashboards

Esta carpeta está vacía a propósito.

Docker la monta dentro del contenedor de Grafana en
`/etc/grafana/provisioning/dashboards/json`, que es la ruta donde el provider
`orderflow` (definido en `../provisioning/dashboards/dashboards.yml`) busca
dashboards.

Todo archivo `.json` que dejes aquí, Grafana lo carga como dashboard en menos de
30 segundos, sin reiniciar nada.

En la Sesión 4 construyes el dashboard en la interfaz de Grafana y luego
exportas su **JSON Model** a esta carpeta. A partir de ese momento el dashboard
deja de vivir solo en la base de datos interna de Grafana y pasa a ser un
archivo del repositorio: se versiona, se revisa y se recrea solo en cualquier
máquina que levante el stack.

Si borras el volumen `grafana_data`, todo lo que hayas hecho a clics desaparece.
Lo que esté en esta carpeta, vuelve.
