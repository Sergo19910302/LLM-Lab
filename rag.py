import os, re, threading
import numpy as np
from llama_cpp import Llama

EMBED_MODEL = os.getenv("EMBED_MODEL_PATH", "models/bge-small-en-v1.5-q8_0.gguf")
DOCS_PATH = os.getenv("DOCS_PATH", "docs/knowledge.md")
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
HEADING = re.compile(r"^\s*(?:\\?#){2}\s+(.*)$")   # '## Title', '  ## Title', '\#\# Title'


def load_chunks(path):
    """Split the knowledge file into pieces: one '## ' section = one chunk."""
    chunks, title, body = [], None, []

    def flush():
        if title:
            text = " ".join(line for line in body if line)
            chunks.append({"title": title, "text": f"{title}. {text}"})

    for line in open(path, encoding="utf-8-sig"):
        m = HEADING.match(line)
        if m:
            flush()
            title, body = m.group(1).strip(), []
        elif title is not None:
            body.append(line.strip())
    flush()
    return chunks


class Retriever:
    def __init__(self, embed_path=EMBED_MODEL, docs_path=DOCS_PATH):
        self.lock = threading.Lock()   # llama.cpp model is not thread-safe
        self.emb = Llama(model_path=embed_path, embedding=True, n_ctx=512, verbose=False)
        self.chunks = load_chunks(docs_path)
        self.vecs = np.array([self._embed(c["text"]) for c in self.chunks])

    def _embed(self, text):
        v = np.array(self.emb.embed(text), dtype=np.float32)
        if v.ndim == 2:            # one vector per token -> average them
            v = v.mean(axis=0)
        return v / np.linalg.norm(v)   # length 1, so dot product = cosine similarity

    def search(self, query, k=2):
        with self.lock:
            q = self._embed(QUERY_PREFIX + query)
        scores = self.vecs @ q
        best = np.argsort(-scores)[:k]
        return [{"title": self.chunks[i]["title"], "text": self.chunks[i]["text"],
                 "score": round(float(scores[i]), 3)} for i in best]