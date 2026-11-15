import os, time, queue, itertools
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from llama_cpp import Llama

MODEL = os.getenv("MODEL_PATH", "models/qwen2.5-0.5b-instruct-q4_k_m.gguf")
N_WORKERS = 1
CORES = max(1, (os.cpu_count() or 2) // 2)
THREADS = max(1, CORES // N_WORKERS)
USE_MMAP = os.getenv("USE_MMAP", "1") == "1"   # 0 = load whole model into RAM

pool = queue.Queue()
for _ in range(N_WORKERS):
    pool.put(Llama(model_path=MODEL, n_ctx=2048,
                   n_threads=THREADS, use_mmap=USE_MMAP, verbose=False))

arrive_counter = itertools.count(1)   # номерок при входе
start_counter = itertools.count(1)    # номер начала обслуживания

app = FastAPI()

class Req(BaseModel):
    prompt: str
    max_tokens: int = 128
    temperature: float = 0.2

@app.get("/health")
def health():
    return {"status": "ok", "pid": os.getpid(), "workers": N_WORKERS,
            "threads_per_worker": THREADS, "free_workers": pool.qsize(),
            "use_mmap": USE_MMAP}

@app.post("/generate")
def generate(r: Req):
    if not r.prompt.strip():
        raise HTTPException(400, "empty prompt")
    arrive_no = next(arrive_counter)
    t_arrive = time.perf_counter()
    llm = pool.get()
    start_no = next(start_counter)
    try:
        t_start = time.perf_counter()
        out = llm.create_chat_completion(
            messages=[{"role": "user", "content": r.prompt}],
            max_tokens=r.max_tokens,
            temperature=r.temperature)
        t_end = time.perf_counter()
    finally:
        pool.put(llm)
    n = out["usage"]["completion_tokens"]
    infer = t_end - t_start
    return {"text": out["choices"][0]["message"]["content"],
            "latency_s": round(t_end - t_arrive, 2),
            "queue_s": round(t_start - t_arrive, 2),
            "infer_s": round(infer, 2),
            "tokens": n,
            "tokens_per_s": round(n / infer, 1),
            "finish_reason": out["choices"][0]["finish_reason"],
            "arrive_no": arrive_no,
            "start_no": start_no}