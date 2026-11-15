import os, time, queue, itertools
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from llama_cpp import Llama
from rag import Retriever

MODEL = os.getenv("MODEL_PATH", "models/qwen2.5-0.5b-instruct-q4_k_m.gguf")
N_WORKERS = 1
CORES = max(1, (os.cpu_count() or 2) // 2)
THREADS = max(1, CORES // N_WORKERS)
USE_MMAP = os.getenv("USE_MMAP", "1") == "1"   # 0 = load whole model into RAM

SYSTEM_RAG = ("You are a reliability engineering assistant. Use the reference notes below "
              "when they are relevant to the question. Answer briefly.\n\nReference notes:\n{notes}")

pool = queue.Queue()
for _ in range(N_WORKERS):
    pool.put(Llama(model_path=MODEL, n_ctx=2048,
                   n_threads=THREADS, use_mmap=USE_MMAP, verbose=False))

retriever = Retriever()               # embedding model + knowledge base, loaded once

arrive_counter = itertools.count(1)   # номерок при входе
start_counter = itertools.count(1)    # номер начала обслуживания

app = FastAPI()

class Req(BaseModel):
    prompt: str
    max_tokens: int = 128
    temperature: float = 0.2
    use_rag: bool = False
    rag_k: int = 2

@app.get("/health")
def health():
    return {"status": "ok", "pid": os.getpid(), "workers": N_WORKERS,
            "threads_per_worker": THREADS, "free_workers": pool.qsize(),
            "use_mmap": USE_MMAP, "rag_chunks": len(retriever.chunks)}

@app.get("/search")
def search(q: str, k: int = 2):
    if not q.strip():
        raise HTTPException(400, "empty query")
    return {"query": q, "results": retriever.search(q, k)}

@app.post("/generate")
def generate(r: Req):
    if not r.prompt.strip():
        raise HTTPException(400, "empty prompt")
    arrive_no = next(arrive_counter)
    t_arrive = time.perf_counter()

    messages = [{"role": "user", "content": r.prompt}]
    sources = []
    if r.use_rag:
        found = retriever.search(r.prompt, r.rag_k)
        sources = [{"title": f["title"], "score": f["score"]} for f in found]
        notes = "\n\n".join(f["text"] for f in found)
        messages.insert(0, {"role": "system", "content": SYSTEM_RAG.format(notes=notes)})
    t_ready = time.perf_counter()

    llm = pool.get()
    start_no = next(start_counter)
    try:
        t_start = time.perf_counter()
        out = llm.create_chat_completion(
            messages=messages,
            max_tokens=r.max_tokens,
            temperature=r.temperature)
        t_end = time.perf_counter()
    finally:
        pool.put(llm)
    n = out["usage"]["completion_tokens"]
    infer = t_end - t_start
    return {"text": out["choices"][0]["message"]["content"],
            "latency_s": round(t_end - t_arrive, 2),
            "rag_s": round(t_ready - t_arrive, 3),
            "queue_s": round(t_start - t_ready, 2),
            "infer_s": round(infer, 2),
            "tokens": n,
            "tokens_per_s": round(n / infer, 1),
            "finish_reason": out["choices"][0]["finish_reason"],
            "arrive_no": arrive_no,
            "start_no": start_no,
            "sources": sources}