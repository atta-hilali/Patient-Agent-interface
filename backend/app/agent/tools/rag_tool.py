# from __future__ import annotations
from __future__ import annotations

# import json
import json
# import os
import os

# import httpx
import httpx
# from langchain_core.tools import tool
from langchain_core.tools import tool

# from app.agent.tools.schemas import GuidelineChunk, GuidelineSearchInput, ToolTextResult, dump_tool_result
from app.agent.tools.schemas import GuidelineChunk, GuidelineSearchInput, ToolTextResult, dump_tool_result


# EMBED_URL = "http://localhost:8006/v1/embeddings"
EMBED_URL = "http://localhost:8006/v1/embeddings"
# RERANK_URL = "http://localhost:8007/v1/rerank"
RERANK_URL = "http://localhost:8007/v1/rerank"
# DB_URL = os.getenv("DATABASE_URL")
DB_URL = os.getenv("DATABASE_URL")
# RAG_TIMEOUT_S = 5.0
RAG_TIMEOUT_S = 5.0


# async def _embed(text: str) -> list[float]:
async def _embed(text: str) -> list[float]:
    # async with httpx.AsyncClient(timeout=RAG_TIMEOUT_S) as client:
    async with httpx.AsyncClient(timeout=RAG_TIMEOUT_S) as client:
        # response = await client.post(EMBED_URL, json={"input": text, "model": "nv-embedqa-e5-v5"})
        response = await client.post(EMBED_URL, json={"input": text, "model": "nv-embedqa-e5-v5"})
        # response.raise_for_status()
        response.raise_for_status()
        # return response.json()["data"][0]["embedding"]
        return response.json()["data"][0]["embedding"]


# async def _rerank(query: str, docs: list[str]) -> list[str]:
async def _rerank(query: str, docs: list[str]) -> list[str]:
    # async with httpx.AsyncClient(timeout=RAG_TIMEOUT_S) as client:
    async with httpx.AsyncClient(timeout=RAG_TIMEOUT_S) as client:
        # response = await client.post(RERANK_URL, json={"query": query, "passages": docs, "top_n": 5})
        response = await client.post(RERANK_URL, json={"query": query, "passages": docs, "top_n": 5})
        # response.raise_for_status()
        response.raise_for_status()
        # rankings = sorted(response.json().get("rankings", []), key=lambda item: item.get("logit", 0), reverse=True)
        rankings = sorted(response.json().get("rankings", []), key=lambda item: item.get("logit", 0), reverse=True)
        # return [docs[item["index"]] for item in rankings[:5] if item.get("index", -1) < len(docs)]
        return [docs[item["index"]] for item in rankings[:5] if item.get("index", -1) < len(docs)]


# @tool(args_schema=GuidelineSearchInput)
@tool(args_schema=GuidelineSearchInput)
# async def search_guidelines(query: str) -> str:
async def search_guidelines(query: str) -> str:
    # """Search the guideline vector index and return the top reranked evidence passages."""
    """Search the guideline vector index and return the top reranked evidence passages."""
    # if not DB_URL:
    if not DB_URL:
        # return dump_tool_result(
        return dump_tool_result(
            # ToolTextResult(tool_name="search_guidelines", summary="Guideline search unavailable because DATABASE_URL is not configured.")
            ToolTextResult(tool_name="search_guidelines", summary="Guideline search unavailable because DATABASE_URL is not configured.")
        # )
        )
    # try:
    try:
        # import asyncpg
        import asyncpg
    # except Exception:  # noqa: BLE001
    except Exception:  # noqa: BLE001
        # return dump_tool_result(
        return dump_tool_result(
            # ToolTextResult(tool_name="search_guidelines", summary="Guideline search unavailable because asyncpg is not installed.")
            ToolTextResult(tool_name="search_guidelines", summary="Guideline search unavailable because asyncpg is not installed.")
        # )
        )

    # q_vec = await _embed(query)
    q_vec = await _embed(query)
    # conn = await asyncpg.connect(DB_URL, timeout=RAG_TIMEOUT_S)
    conn = await asyncpg.connect(DB_URL, timeout=RAG_TIMEOUT_S)
    # try:
    try:
        # rows = await conn.fetch(
        rows = await conn.fetch(
            # "SELECT content FROM guidelines ORDER BY embedding <=> $1::vector LIMIT 20",
            "SELECT content FROM guidelines ORDER BY embedding <=> $1::vector LIMIT 20",
            # json.dumps(q_vec),
            json.dumps(q_vec),
            # timeout=RAG_TIMEOUT_S,
            timeout=RAG_TIMEOUT_S,
        # )
        )
    # finally:
    finally:
        # await conn.close()
        await conn.close()

    # docs = [row["content"] for row in rows]
    docs = [row["content"] for row in rows]
    # if not docs:
    if not docs:
        # return dump_tool_result(ToolTextResult(tool_name="search_guidelines", summary="No guideline passages found."))
        return dump_tool_result(ToolTextResult(tool_name="search_guidelines", summary="No guideline passages found."))

    # top_five = await _rerank(query, docs)
    top_five = await _rerank(query, docs)
    # chunks = [
    chunks = [
        # GuidelineChunk(chunk_id=f"RAG-{index}", content=chunk)
        GuidelineChunk(chunk_id=f"RAG-{index}", content=chunk)
        # for index, chunk in enumerate(top_five, start=1)
        for index, chunk in enumerate(top_five, start=1)
    # ]
    ]
    # summary = "\n---\n".join(f"[{chunk.chunk_id}] {chunk.content}" for chunk in chunks)
    summary = "\n---\n".join(f"[{chunk.chunk_id}] {chunk.content}" for chunk in chunks)
    # return dump_tool_result(
    return dump_tool_result(
        # ToolTextResult(
        ToolTextResult(
            # tool_name="search_guidelines",
            tool_name="search_guidelines",
            # summary=summary,
            summary=summary,
            # data={"guideline_chunks": [chunk.model_dump(mode="json") for chunk in chunks]},
            data={"guideline_chunks": [chunk.model_dump(mode="json") for chunk in chunks]},
        # )
        )
    # )
    )
