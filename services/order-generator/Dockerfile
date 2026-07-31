FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias primero (mejor cache de layers)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar codigo
COPY generator.py .

# Puerto del endpoint /metrics de Prometheus
EXPOSE 8000

CMD ["python", "-u", "generator.py"]
