from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from loguru import logger
from .config import settings
from .loader import load_and_flatten
from .chunking import chunk_entries
from .embedder import generate_embeddings, generate_embedding
from .retriever import ChromaStore
from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .llm import generate_answer
import uvicorn
from typing import List


app = FastAPI(title="Travel Knowledge Base RAG")
store = ChromaStore()


class EmbedRequest(BaseModel):
    data_dir: str = "./data"
    chunk_size: int | None = None
    overlap: int | None = None


class AskRequest(BaseModel):
    question: str
    top_k: int | None = None
    rerank: bool = False


@app.post('/embed_data')
def embed_data(req: EmbedRequest):
    # Step 1: load
    entries = load_and_flatten(req.data_dir)
    chunk_size = req.chunk_size or settings.CHUNK_SIZE_CHARS
    overlap = req.overlap or settings.CHUNK_OVERLAP_CHARS
    # Step 2: chunk
    chunks = chunk_entries(entries, chunk_size=chunk_size, overlap=overlap)

    docs = [c['text'] for c in chunks]
    metadatas = [c['metadata'] for c in chunks]
    ids = [m['chunk_id'] for m in metadatas]

    # Step 3: embeddings
    embeddings = generate_embeddings(docs)

    # Step 4: store
    store.rebuild(documents=docs, embeddings=embeddings, metadatas=metadatas, ids=ids)

    return {"status": "ok", "documents_indexed": len(docs)}


@app.post('/ask')
def ask(req: AskRequest):
    top_k = req.top_k or settings.DEFAULT_TOP_K
    q_emb = generate_embedding(req.question)
    results = store.query(q_emb, top_k=top_k, rerank=req.rerank)

    # Build context block
    context_items = []
    sources = []
    chunks_used = []
    for i, r in enumerate(results):
        m = r['metadata']
        chunk_id = m.get('chunk_id')
        chunks_used.append(chunk_id)
        sources.append(m.get('source_file'))
        context_items.append(f"[{i+1}] (chunk_id={chunk_id}) (country={m.get('country')}) (category={m.get('category')})\n" + r['document'])

    context_block = "\n\n".join(context_items)
    user_prompt = USER_PROMPT_TEMPLATE.format(context=context_block, question=req.question)

    # call LLM
    try:
        answer_text = generate_answer(SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        logger.exception("LLM call failed")
        raise HTTPException(status_code=500, detail=str(e))

    # return structured response
    return {"answer": answer_text, "sources": list(dict.fromkeys(sources)), "chunks_used": chunks_used}


@app.get('/health')
def health():
    return {"status": "ok", "chroma_collection": store.collection.name}


if __name__ == '__main__':
    uvicorn.run('src.main:app', host=settings.HOST, port=settings.PORT, reload=True)
