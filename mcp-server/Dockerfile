FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8100

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py backend_client.py ./

RUN addgroup --system app && adduser --system --ingroup app --no-create-home app \
    && chown -R app:app /app
USER app

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,os,sys; sys.exit(0) if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8100\")}/health', timeout=3).status==200 else sys.exit(1)"

CMD ["python", "server.py"]
