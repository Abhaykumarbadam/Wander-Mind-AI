from typing import List, Dict, Optional
import os
from loguru import logger

from .config import settings
from .loader import load_and_flatten
from .chunking import chunk_entries
from .embedder import generate_embeddings, generate_embedding
from .retriever import ChromaStore
from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .llm import generate_answer as llm_generate_answer
# Prefer the existing app-level core.llm.chat (uses LangChain wrapper) if available — it's used by `app.py` and is known to work
try:
    from core.llm import chat as core_chat
except Exception:
    core_chat = None


# Initialize a Chroma store singleton for this module
_STORE: Optional[ChromaStore] = None


def _get_store() -> ChromaStore:
    global _STORE
    if _STORE is None:
        _STORE = ChromaStore(collection_name=settings.CHROMA_COLLECTION_NAME)
    return _STORE


def ingest(data_dir: str = "./data", chunk_size: Optional[int] = None, overlap: Optional[int] = None) -> Dict:
    """Load files under data_dir, chunk, embed and store into Chroma.

    Returns simple stats dict.
    """
    if not os.path.isdir(data_dir):
        raise ValueError(f"data_dir not found: {data_dir}")

    chunk_size = chunk_size or settings.CHUNK_SIZE_CHARS
    overlap = overlap or settings.CHUNK_OVERLAP_CHARS

    entries = load_and_flatten(data_dir)
    chunks = chunk_entries(entries, chunk_size=chunk_size, overlap=overlap)

    docs = [c['text'] for c in chunks]
    metadatas = [c['metadata'] for c in chunks]
    ids = [m['chunk_id'] for m in metadatas]

    if not docs:
        return {"inserted": 0}

    logger.info(f"Generating embeddings for {len(docs)} chunks")
    embeddings = generate_embeddings(docs)

    store = _get_store()
    store.rebuild(documents=docs, embeddings=embeddings, metadatas=metadatas, ids=ids)

    return {"inserted": len(docs)}


def generate_answer(question: str, top_k: Optional[int] = None, rerank: bool = False) -> Dict:
    """Run a retrieval over Chroma and call the LLM with the constructed context.

    Returns dict: {answer: str, sources: list, chunks_used: list}
    """
    top_k = int(top_k or settings.DEFAULT_TOP_K)
    store = _get_store()

    q_emb = generate_embedding(question)
    results = store.query(q_emb, top_k=top_k, rerank=rerank)

    # Build context items like src.main
    context_items = []
    sources = []
    chunks_used = []
    for i, r in enumerate(results):
        m = r.get('metadata', {})
        chunk_id = m.get('chunk_id')
        chunks_used.append(chunk_id)
        sources.append(m.get('source_file'))
        context_items.append(f"[{i+1}] (chunk_id={chunk_id}) (country={m.get('country')}) (category={m.get('category')})\n" + r.get('document', ''))

    context_block = "\n\n".join(context_items)
    user_prompt = USER_PROMPT_TEMPLATE.format(context=context_block, question=question)

    try:
        # Use the core.chat wrapper (LangChain Google GenAI) if available since
        # it is already wired and tested in the app. Fall back to the local llm wrapper.
        if core_chat is not None:
            msgs = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
            answer_text = core_chat(msgs, temperature=0.0, max_tokens=800)
        else:
            answer_text = llm_generate_answer(SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        logger.exception("LLM call failed in RAG.generate_answer")
        raise

    return {"answer": answer_text, "sources": list(dict.fromkeys([s for s in sources if s])), "chunks_used": chunks_used}


def retrieve(question: str, top_k: Optional[int] = None, rerank: bool = False) -> List[Dict]:
    """Return raw retrieval results (no LLM call). Each item: {id, document, metadata, distance}"""
    top_k = int(top_k or settings.DEFAULT_TOP_K)
    store = _get_store()
    q_emb = generate_embedding(question)
    results = store.query(q_emb, top_k=top_k, rerank=rerank)
    return results


def generate_answer_single_call(question: str, top_k: Optional[int] = None, rerank: bool = False) -> Dict:
    """Perform retrieval and then a single LLM call that consumes the retrieved raw documents.

    Returns the same shape as generate_answer: {answer, sources, chunks_used}
    """
    top_k = int(top_k or settings.DEFAULT_TOP_K)
    results = retrieve(question, top_k=top_k, rerank=rerank)

    context_items = []
    sources = []
    chunks_used = []
    for i, r in enumerate(results):
        m = r.get('metadata', {})
        chunk_id = m.get('chunk_id')
        chunks_used.append(chunk_id)
        sources.append(m.get('source_file'))
        context_items.append(f"[{i+1}] (chunk_id={chunk_id}) (country={m.get('country')}) (category={m.get('category')})\n" + r.get('document', ''))

    context_block = "\n\n".join(context_items)
    user_prompt = USER_PROMPT_TEMPLATE.format(context=context_block, question=question)

    try:
        if core_chat is not None:
            msgs = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
            answer_text = core_chat(msgs, temperature=0.0, max_tokens=800)
        else:
            answer_text = llm_generate_answer(SYSTEM_PROMPT, user_prompt)
    except Exception:
        logger.exception("LLM call failed in RAG.generate_answer_single_call")
        raise

    return {"answer": answer_text, "sources": list(dict.fromkeys([s for s in sources if s])), "chunks_used": chunks_used}
