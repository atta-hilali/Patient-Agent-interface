from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.rag.service import get_rag_service

router = APIRouter(prefix="/rag", tags=["rag"])


class RagIngestDocument(BaseModel):
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagIngestRequest(BaseModel):
    clinic_id: str = Field(min_length=1)
    specialty: str = Field(min_length=1)
    source: str = "manual_ingest"
    documents: list[RagIngestDocument] = Field(default_factory=list)


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    clinic_id: str = Field(min_length=1)
    specialty: str = Field(min_length=1)


@router.get("/health")
async def rag_health() -> dict[str, Any]:
    service = get_rag_service()
    return await service.health()


@router.post("/ingest")
async def rag_ingest(request: RagIngestRequest) -> dict[str, Any]:
    service = get_rag_service()
    try:
        return await service.ingest_documents(
            documents=[item.model_dump(mode="json") for item in request.documents],
            clinic_id=request.clinic_id,
            specialty=request.specialty,
            source=request.source,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"RAG ingest failed: {exc}") from exc


@router.post("/search")
async def rag_search(request: RagSearchRequest) -> dict[str, Any]:
    service = get_rag_service()
    try:
        return await service.search(
            query=request.query,
            clinic_id=request.clinic_id,
            specialty=request.specialty,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"RAG search failed: {exc}") from exc

