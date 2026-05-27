FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data /app/output

VOLUME ["/app/data", "/app/output"]

ENTRYPOINT ["python", "main.py"]
CMD ["--daemon"]
