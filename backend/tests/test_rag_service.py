from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.rag.service import RagService


@dataclass
class _FakeRagSettings:
    rag_enabled: bool = True
    database_url: str = ""
    rag_embed_url: str = "http://embed.local/v1/embeddings"
    rag_rerank_url: str = "http://rerank.local/v1/rerank"
    rag_timeout_sec: int = 5
    rag_top_k: int = 10
    rag_rerank_top_n: int = 5
    rag_chunk_size: int = 20
    rag_chunk_overlap: int = 5


def test_chunk_document_dedupes_and_windows():
    service = RagService(_FakeRagSettings())
    text = " ".join(["alpha"] * 80) + ". " + " ".join(["beta"] * 80)
    chunks = service._chunk_document(text)

    assert len(chunks) >= 2
    assert all(len(chunk.split()) <= service.chunk_size for chunk in chunks)
    assert len(chunks) == len(set(chunks))


def test_fallback_rerank_prefers_overlap():
    service = RagService(_FakeRagSettings())
    ranked = service._fallback_rerank(
        "medication timing after meal",
        [
            "schedule appointment and billing details",
            "medication timing with food and after meal guidance",
            "weather and travel",
        ],
    )
    # The medication-related document should rank first.
    assert ranked
    assert ranked[0][0] == 1


def test_search_returns_disabled_payload_when_rag_disabled():
    settings = _FakeRagSettings(rag_enabled=False)
    service = RagService(settings)

    response = asyncio.run(service.search(query="test", clinic_id="demo", specialty="general_medicine"))
    assert response["results"] == []
    assert "disabled" in response["meta"]["error"].lower()


def test_ingest_returns_disabled_payload_when_rag_disabled():
    settings = _FakeRagSettings(rag_enabled=False)
    service = RagService(settings)

    response = asyncio.run(
        service.ingest_documents(
            documents=[{"title": "Doc", "text": "Example guideline text"}],
            clinic_id="demo",
            specialty="general_medicine",
        )
    )
    assert response["inserted"] == 0
    assert response["chunks"] == 0
    assert response["errors"]
