from typing import List, Tuple
import re
from loguru import logger


def split_into_sentences(text: str) -> List[str]:
    # Simple sentence splitter; avoids heavy deps
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    """Chunk text into approximately chunk_size characters with overlap.

    This is a heuristic: we accumulate sentences until we reach the target size.
    """
    sentences = split_into_sentences(text)
    chunks = []
    cur = []
    cur_len = 0
    for s in sentences:
        s_len = len(s) + 1
        if cur_len + s_len > chunk_size and cur:
            chunk_text = ' '.join(cur).strip()
            chunks.append(chunk_text)
            # prepare overlap
            # take last tokens of current chunk for overlap (by characters)
            if overlap > 0:
                overlap_text = ''
                acc = ''
                for token in reversed(cur):
                    if len(acc) + len(token) + 1 > overlap:
                        break
                    acc = token + ' ' + acc
                cur = [acc.strip()] if acc.strip() else []
                cur_len = len(' '.join(cur))
            else:
                cur = []
                cur_len = 0
        cur.append(s)
        cur_len += s_len

    if cur:
        chunks.append(' '.join(cur).strip())

    logger.debug(f"Chunked text into {len(chunks)} pieces (chunk_size={chunk_size})")
    return chunks


def chunk_entries(entries: List[dict], chunk_size: int = 1200, overlap: int = 200):
    out = []
    for i, e in enumerate(entries):
        text = e['text']
        meta = e['metadata']
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        for idx, c in enumerate(chunks):
            cm = dict(meta)
            cm['chunk_id'] = f"{meta.get('country','unknown')}::{meta.get('category','') }::{i}::{idx}"
            out.append({'text': c, 'metadata': cm})
    return out
