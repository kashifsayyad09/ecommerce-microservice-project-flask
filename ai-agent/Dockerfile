FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8200

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py auth.py mcp_client.py tools.py system_prompt.py ./
COPY providers/ ./providers/

RUN addgroup --system app && adduser --system --ingroup app --no-create-home app \
    && chown -R app:app /app
USER app

EXPOSE 8200

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,os,sys; sys.exit(0) if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8200\")}/health', timeout=3).status==200 else sys.exit(1)"

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
