# llm-lab

A small local LLM inference service with a C# test client focused on **reliability testing**.

A quantized Qwen2.5-0.5B model runs behind a REST API (FastAPI + llama.cpp). A C# console client checks the service for correctness, performance, fairness and long-run stability.

## Architecture

```
C# test client  --HTTP-->  FastAPI server  -->  worker pool (queue.Queue)  -->  llama.cpp + Qwen2.5-0.5B (GGUF, q4_k_m)
(LlmClient)                (server.py)          FIFO queue                     CPU inference
```

## Stack

| Part | Technology |
|---|---|
| Inference engine | llama-cpp-python 0.3.36 (CPU) |
| Model | Qwen2.5-0.5B-Instruct, GGUF q4_k_m (~400 MB) |
| API | FastAPI + uvicorn |
| Test client | C# / .NET 10 |
| Packaging | Docker, Docker Compose |

## API

| Endpoint | Description |
|---|---|
| `GET /health` | Status, worker count, threads, PID |
| `POST /generate` | Body: `{"prompt": "...", "max_tokens": 128}`. Returns the text and metrics: `queue_s`, `infer_s`, `tokens`, `tokens_per_s`, `finish_reason`, `arrive_no`, `start_no` |

An empty prompt returns `400`.

## Quick start

1. Download the model into `models/`:
   ```
   python -c "from huggingface_hub import hf_hub_download; hf_hub_download('Qwen/Qwen2.5-0.5B-Instruct-GGUF', 'qwen2.5-0.5b-instruct-q4_k_m.gguf', local_dir='models')"
   ```
2. Start the server:
   ```
   docker compose up -d --build
   docker compose ps          # wait for "healthy"
   ```
3. Open the API docs: http://127.0.0.1:8000/docs

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `MODEL_PATH` | `models/qwen2.5-0.5b-instruct-q4_k_m.gguf` | Path to the GGUF model |
| `USE_MMAP` | `1` | `0` = load the whole model into RAM |

## Tests

Run from the `LlmClient` folder:

| Command | What it checks |
|---|---|
| `dotnet run -- basic` | Health check, empty prompt → 400, 5 parallel requests (queue and generation time) |
| `dotnet run -- fairness` | 8 requests 50 ms apart: are they served in arrival order (FIFO)? |
| `dotnet run -- soak 30` | 30-minute endurance run. Writes `soak.csv` with one row per minute: requests, errors, avg / p95 / max latency, tokens/s, server memory |

## Results (baseline)

Hardware: laptop, Intel Core i7-1165G7 (4 cores / 8 threads), Windows 11, CPU only.

| Test | Native (Windows) | Docker Desktop (WSL2) |
|---|---|---|
| Generation speed | ~46 tokens/s | ~17–43 tokens/s |
| 5 parallel requests, total time | ~5.5 s | ~11.3 s |
| Fairness (FIFO) | PASS | PASS |
| Soak, 30 min | **PASS**: 1148 requests, 0 errors, memory stable (477–567 MB), no degradation | not run yet |

### Scaling experiment

Two model instances on the same CPU (`N_WORKERS = 2`) made things **worse**: 6.0 s instead of 5.5 s. Each instance ran at half speed (~23 tokens/s), so the total throughput stayed at ~46 tokens/s. On CPU, generation is limited by memory bandwidth. Real gains need batching, a GPU, or more machines.

## Findings

Defects and issues found and fixed during testing:

1. **2-second connection delay.** The client used `localhost`; Windows tried IPv6 (`::1`) first while the server listened only on IPv4. New connections waited ~2 s. Fix: use `127.0.0.1`.
2. **Unfair queue.** With `threading.Lock`, requests were not guaranteed to be served in order. Fix: worker pool on `queue.Queue` (verified by the fairness test).
3. **Misleading metrics.** The server timer started before the queue, so tokens/s looked lower under load. Fix: separate `queue_s` and `infer_s`.
4. **Test stand: laptop went to sleep.** One soak run recorded a 902-second request with 0 errors. Root cause: system sleep, not the service. Fix: the client keeps Windows awake during soak tests.
5. **Noisy neighbour.** During the soak test, other programs on the laptop cut speed by about a third for several minutes. The service recovered on its own with no errors.
6. **Docker on Windows is ~2x slower.** The container received about 2.3 CPU cores out of 4 (`docker stats`). Expected to be close to native on a Linux host.

## Project structure

```
llm-lab/
├── server.py            # FastAPI + llama.cpp server
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── models/              # GGUF model (not in git)
└── LlmClient/           # C# test client
    ├── Program.cs
    └── LlmClient.csproj
```
