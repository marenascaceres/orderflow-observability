FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY processor.py .

# Puerto del endpoint /metrics de Prometheus
EXPOSE 8001

CMD ["python", "-u", "processor.py"]
