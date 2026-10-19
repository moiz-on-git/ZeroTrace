"""
Support Copilot — RAG-based Q&A over Kaveri Finserv data.

If ZT_LLM_PROVIDER is configured: uses the LLM to generate answers.
Otherwise: extractive fallback — returns the retrieved chunk text directly.
This ensures the demo works with no network.
"""
from __future__ import annotations

import json
from typing import Any

from src.core.config import get_settings
from src.core.logging import get_logger
from src.seed.vector_seeder import get_embedding_model

logger = get_logger("copilot")
cfg = get_settings()


def answer_query(question: str, top_k: int = 3) -> str:
    """
    Retrieve top-k chunks for the question and return an answer.
    """
    import psycopg

    pg_dsn = (
        f"host={cfg.pg_host} port={cfg.pg_port} "
        f"dbname={cfg.pg_db_rag} "
        f"user={cfg.pg_user} password={cfg.pg_password}"
    )

    model = get_embedding_model()
    embedding = model.encode([question], show_progress_bar=False)[0].tolist()

    chunks: list[str] = []
    try:
        with psycopg.connect(pg_dsn) as conn:
            cur = conn.execute(
                """
                SELECT content, 1 - (embedding <=> %s::vector) AS similarity
                FROM embeddings
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (embedding, embedding, top_k),
            )
            for row in cur.fetchall():
                content, sim = row
                if sim > 0.3:
                    chunks.append(content)
    except Exception as e:
        logger.warning("copilot.retrieval_failed", error=str(e))
        return "Unable to retrieve information at this time."

    if not chunks:
        return "No relevant information found."

    # LLM path
    if cfg.llm_provider and cfg.llm_api_key:
        return _llm_answer(question, chunks)

    # Extractive fallback — return retrieved text
    context = "\n\n---\n\n".join(chunks[:top_k])
    return f"[Extractive answer based on retrieved context]\n\n{context}"


def _llm_answer(question: str, chunks: list[str]) -> str:
    """Call an LLM to generate a grounded answer. Falls back to extractive on error."""
    context = "\n\n".join(chunks)
    prompt = (
        f"You are a helpful customer support agent for Kaveri Finserv. "
        f"Answer the following question using only the provided context. "
        f"Do not reveal personal data unless explicitly in the context.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        f"Answer:"
    )

    try:
        import httpx
        resp = httpx.post(
            f"{cfg.llm_provider}/v1/completions",
            headers={"Authorization": f"Bearer {cfg.llm_api_key}"},
            json={"model": cfg.llm_model, "prompt": prompt, "max_tokens": 256},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["text"].strip()
    except Exception as e:
        logger.warning("copilot.llm_failed", error=str(e))
        return f"[Extractive fallback]\n\n{chunks[0]}" if chunks else "No answer available."
