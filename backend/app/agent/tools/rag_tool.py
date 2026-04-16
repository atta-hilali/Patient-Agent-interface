from __future__ import annotations

from langchain_core.tools import tool

from app.agent.tools.schemas import GuidelineChunk, GuidelineSearchInput, ToolTextResult, dump_tool_result
from app.connectors import ConnectorStore
from app.config import get_settings
from app.rag.service import get_rag_service


async def _resolve_scope() -> tuple[str, str]:
    """
    Resolve clinic and specialty scope from the default connector used in this turn.
    This keeps RAG retrieval specialty-aware while preserving backward compatibility.
    """
    settings = get_settings()
    store = ConnectorStore(settings)
    connector = await store.get("demo-clinic")
    clinic_id = connector.clinic_id
    specialty = connector.specialty or "general_medicine"
    return clinic_id, specialty


@tool(args_schema=GuidelineSearchInput)
async def search_guidelines(query: str) -> str:
    """Search clinic- and specialty-scoped guideline chunks with rerank and fallback."""
    service = get_rag_service()
    clinic_id, specialty = await _resolve_scope()
    try:
        response = await service.search(query=query, clinic_id=clinic_id, specialty=specialty)
    except Exception as exc:  # noqa: BLE001
        return dump_tool_result(
            ToolTextResult(
                tool_name="search_guidelines",
                summary=f"Guideline search unavailable: {exc}",
            )
        )

    rows = response.get("results", [])
    if not isinstance(rows, list) or not rows:
        return dump_tool_result(ToolTextResult(tool_name="search_guidelines", summary="No guideline passages found."))

    chunks: list[GuidelineChunk] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        chunks.append(
            GuidelineChunk(
                chunk_id=str(row.get("chunk_id") or f"RAG-{len(chunks) + 1}"),
                content=str(row.get("content") or ""),
            )
        )

    summary = "\n---\n".join(f"[{chunk.chunk_id}] {chunk.content}" for chunk in chunks)
    return dump_tool_result(
        ToolTextResult(
            tool_name="search_guidelines",
            summary=summary,
            data={
                "guideline_chunks": [chunk.model_dump(mode="json") for chunk in chunks],
                "meta": response.get("meta", {}),
            },
        )
    )

