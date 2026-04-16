from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

try:
    import asyncpg
except Exception:  # noqa: BLE001
    asyncpg = None


@dataclass
class RagChunk:
    chunk_id: str
    content: str
    source: str
    clinic_id: str
    specialty: str
    metadata: dict[str, Any]


@dataclass
class RagSearchResult:
    chunk_id: str
    content: str
    score: float
    source: str
    metadata: dict[str, Any]


def _normalize_text(value: str) -> str:
    return " ".join((value or "").replace("\u00a0", " ").split())


class RagService:
    """
    Production-oriented RAG service:
    - deterministic chunking + dedupe
    - embedding + vector retrieval
    - rerank with fallback scoring
    - structured diagnostics for operations
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.rag_enabled
        self.database_url = settings.database_url
        self.embed_url = settings.rag_embed_url
        self.rerank_url = settings.rag_rerank_url
        self.timeout = float(max(settings.rag_timeout_sec, 1))
        self.top_k = max(settings.rag_top_k, 1)
        self.top_n = max(settings.rag_rerank_top_n, 1)
        self.chunk_size = max(settings.rag_chunk_size, 128)
        self.chunk_overlap = max(min(settings.rag_chunk_overlap, self.chunk_size - 1), 0)

    def _chunk_document(self, text: str) -> list[str]:
        content = _normalize_text(text)
        if not content:
            return []

        # Section-aware split first; fallback to fixed-size windows.
        sections = re.split(r"\n{2,}|(?<=\.)\s+(?=[A-Z])", content)
        cleaned_sections = [_normalize_text(section) for section in sections if _normalize_text(section)]
        if not cleaned_sections:
            cleaned_sections = [content]

        out: list[str] = []
        for section in cleaned_sections:
            if len(section.split()) <= self.chunk_size:
                out.append(section)
                continue

            words = section.split()
            step = self.chunk_size - self.chunk_overlap
            for start in range(0, len(words), step):
                window = words[start : start + self.chunk_size]
                if not window:
                    continue
                out.append(" ".join(window))
                if start + self.chunk_size >= len(words):
                    break

        deduped: list[str] = []
        seen: set[str] = set()
        for chunk in out:
            key = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
            if key in seen:
                continue
            seen.add(key)
            if len(chunk) < 40:
                continue
            deduped.append(chunk)
        return deduped

    async def _embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.embed_url, json={"input": text, "model": "nv-embedqa-e5-v5"})
            response.raise_for_status()
            payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or not data:
            raise RuntimeError("Embedding response missing data.")
        vector = (data[0] or {}).get("embedding")
        if not isinstance(vector, list) or not vector:
            raise RuntimeError("Embedding vector missing.")
        return [float(value) for value in vector]

    async def _rerank(self, query: str, docs: list[str]) -> list[tuple[int, float]]:
        if not docs:
            return []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.rerank_url,
                json={"query": query, "passages": docs, "top_n": min(self.top_n, len(docs))},
            )
            response.raise_for_status()
            payload = response.json()

        rankings = payload.get("rankings") if isinstance(payload, dict) else None
        if not isinstance(rankings, list):
            return []

        scored: list[tuple[int, float]] = []
        for item in rankings:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            score = item.get("logit", item.get("score", 0))
            if not isinstance(index, int):
                continue
            try:
                scored.append((index, float(score)))
            except Exception:  # noqa: BLE001
                continue
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[: self.top_n]

    def _fallback_rerank(self, query: str, docs: list[str]) -> list[tuple[int, float]]:
        q_tokens = set(_normalize_text(query).lower().split())
        if not q_tokens:
            return [(idx, 0.0) for idx in range(min(self.top_n, len(docs)))]
        scored: list[tuple[int, float]] = []
        for index, doc in enumerate(docs):
            d_tokens = set(_normalize_text(doc).lower().split())
            overlap = len(q_tokens & d_tokens)
            norm = math.sqrt(max(len(q_tokens), 1) * max(len(d_tokens), 1))
            score = overlap / norm if norm else 0.0
            scored.append((index, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[: self.top_n]

    async def _connect(self):
        if asyncpg is None:
            raise RuntimeError("asyncpg is not installed.")
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is not configured.")
        return await asyncpg.connect(self.database_url, timeout=self.timeout)

    async def health(self) -> dict[str, Any]:
        status = {"enabled": self.enabled, "database": False, "embedding": False, "reranker": False, "errors": []}
        if not self.enabled:
            return status

        try:
            conn = await self._connect()
            await conn.fetchval("SELECT 1")
            await conn.close()
            status["database"] = True
        except Exception as exc:  # noqa: BLE001
            status["errors"].append(f"database:{exc}")

        try:
            await self._embed("health probe")
            status["embedding"] = True
        except Exception as exc:  # noqa: BLE001
            status["errors"].append(f"embedding:{exc}")

        try:
            await self._rerank("health probe", ["one", "two"])
            status["reranker"] = True
        except Exception as exc:  # noqa: BLE001
            status["errors"].append(f"reranker:{exc}")
        return status

    async def ingest_documents(
        self,
        *,
        documents: list[dict[str, Any]],
        clinic_id: str,
        specialty: str,
        source: str = "manual_ingest",
    ) -> dict[str, Any]:
        if not self.enabled:
            return {"inserted": 0, "chunks": 0, "errors": ["RAG is disabled."]}
        if not documents:
            return {"inserted": 0, "chunks": 0, "errors": ["No documents supplied."]}

        start = time.perf_counter()
        conn = await self._connect()
        inserted = 0
        chunks_total = 0
        errors: list[str] = []

        try:
            for doc in documents:
                title = _normalize_text(str(doc.get("title") or "Untitled"))
                text = _normalize_text(str(doc.get("text") or ""))
                metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
                chunks = self._chunk_document(text)
                chunks_total += len(chunks)

                for index, chunk in enumerate(chunks, start=1):
                    try:
                        embedding = await self._embed(chunk)
                        chunk_id = hashlib.sha256(f"{clinic_id}:{title}:{index}:{chunk}".encode("utf-8")).hexdigest()
                        await conn.execute(
                            """
                            INSERT INTO guidelines
                                (chunk_id, clinic_id, specialty, source, title, content, metadata, embedding, updated_at)
                            VALUES
                                ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::vector, NOW())
                            ON CONFLICT (chunk_id) DO UPDATE
                            SET content = EXCLUDED.content,
                                metadata = EXCLUDED.metadata,
                                embedding = EXCLUDED.embedding,
                                updated_at = NOW()
                            """,
                            chunk_id,
                            clinic_id,
                            specialty,
                            source,
                            title,
                            chunk,
                            json.dumps(metadata, ensure_ascii=True),
                            json.dumps(embedding, ensure_ascii=True),
                        )
                        inserted += 1
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"{title}#{index}:{exc}")
        finally:
            await conn.close()

        return {
            "inserted": inserted,
            "chunks": chunks_total,
            "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            "errors": errors[:20],
        }

    async def search(
        self,
        *,
        query: str,
        clinic_id: str,
        specialty: str,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {"results": [], "meta": {"error": "RAG is disabled."}}

        start = time.perf_counter()
        query_vector = await self._embed(query)
        conn = await self._connect()
        rows = []
        try:
            rows = await conn.fetch(
                """
                SELECT chunk_id, source, content, metadata, 1 - (embedding <=> $1::vector) AS score
                FROM guidelines
                WHERE (clinic_id = $2 OR clinic_id = 'global')
                  AND (specialty = $3 OR specialty = 'general')
                ORDER BY embedding <=> $1::vector
                LIMIT $4
                """,
                json.dumps(query_vector, ensure_ascii=True),
                clinic_id,
                specialty,
                self.top_k,
                timeout=self.timeout,
            )
        finally:
            await conn.close()

        docs = [str(row["content"] or "") for row in rows]
        rerank_used = "model"
        try:
            ranked = await self._rerank(query, docs)
            if not ranked:
                raise RuntimeError("Rerank response empty.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("RAG reranker fallback triggered: %r", exc)
            ranked = self._fallback_rerank(query, docs)
            rerank_used = "fallback"

        results: list[RagSearchResult] = []
        for index, score in ranked:
            if index >= len(rows):
                continue
            row = rows[index]
            metadata = row["metadata"] if isinstance(row["metadata"], dict) else {}
            results.append(
                RagSearchResult(
                    chunk_id=str(row["chunk_id"] or f"RAG-{index + 1}"),
                    content=str(row["content"] or ""),
                    score=float(score),
                    source=str(row["source"] or ""),
                    metadata=metadata,
                )
            )

        return {
            "results": [
                {
                    "chunk_id": item.chunk_id,
                    "content": item.content,
                    "score": round(item.score, 6),
                    "source": item.source,
                    "metadata": item.metadata,
                }
                for item in results
            ],
            "meta": {
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                "rerank_used": rerank_used,
                "candidate_count": len(rows),
                "returned_count": len(results),
            },
        }


_rag_service: RagService | None = None


def get_rag_service() -> RagService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RagService(get_settings())
    return _rag_service

