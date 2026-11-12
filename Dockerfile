FROM python:3.12-slim

# Compiler for llama.cpp (in case no ready-made wheel exists)
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

COPY server.py .

ENV MODEL_PATH=/app/models/qwen2.5-0.5b-instruct-q4_k_m.gguf
EXPOSE 8000

# Docker checks our /health endpoint by itself
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
