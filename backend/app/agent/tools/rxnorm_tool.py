# from __future__ import annotations
from __future__ import annotations

# import time
import time

# import httpx
import httpx
# from langchain_core.tools import tool
from langchain_core.tools import tool

# from app.agent.tools.schemas import InteractionRecord, InteractionToolInput, ToolTextResult, dump_tool_result
from app.agent.tools.schemas import InteractionRecord, InteractionToolInput, ToolTextResult, dump_tool_result
# from app.cache import read_context_for_session
from app.cache import read_context_for_session

# try:
try:
    # from redis.asyncio import Redis
    from redis.asyncio import Redis
# except Exception:  # noqa: BLE001
except Exception:  # noqa: BLE001
    # Redis = None
    Redis = None


# _memory_cache: dict[str, tuple[float, str]] = {}
_memory_cache: dict[str, tuple[float, str]] = {}
# _redis_client = None
_redis_client = None
# RXNORM_TIMEOUT_S = 5.0
RXNORM_TIMEOUT_S = 5.0


# def _get_redis():
def _get_redis():
    # global _redis_client
    global _redis_client
    # if _redis_client is not None:
    if _redis_client is not None:
        # return _redis_client
        return _redis_client
    # if Redis is None:
    if Redis is None:
        # return None
        return None
    # try:
    try:
        # from app.config import get_settings
        from app.config import get_settings

        # settings = get_settings()
        settings = get_settings()
        # if settings.redis_url:
        if settings.redis_url:
            # _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
            _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    # except Exception:  # noqa: BLE001
    except Exception:  # noqa: BLE001
        # _redis_client = None
        _redis_client = None
    # return _redis_client
    return _redis_client


# async def _cache_get(key: str) -> str | None:
async def _cache_get(key: str) -> str | None:
    # redis = _get_redis()
    redis = _get_redis()
    # if redis is not None:
    if redis is not None:
        # try:
        try:
            # cached = await redis.get(key)
            cached = await redis.get(key)
            # if cached:
            if cached:
                # return cached
                return cached
        # except Exception:  # noqa: BLE001
        except Exception:  # noqa: BLE001
            # pass
            pass
    # cached = _memory_cache.get(key)
    cached = _memory_cache.get(key)
    # if not cached or cached[0] < time.time():
    if not cached or cached[0] < time.time():
        # _memory_cache.pop(key, None)
        _memory_cache.pop(key, None)
        # return None
        return None
    # return cached[1]
    return cached[1]


# async def _cache_set(key: str, value: str) -> None:
async def _cache_set(key: str, value: str) -> None:
    # redis = _get_redis()
    redis = _get_redis()
    # if redis is not None:
    if redis is not None:
        # try:
        try:
            # await redis.set(key, value, ex=3600)
            await redis.set(key, value, ex=3600)
            # return
            return
        # except Exception:  # noqa: BLE001
        except Exception:  # noqa: BLE001
            # pass
            pass
    # _memory_cache[key] = (time.time() + 3600, value)
    _memory_cache[key] = (time.time() + 3600, value)


# async def _resolve_rxcuis(rxcuis: list[str], session_id: str | None) -> list[str]:
async def _resolve_rxcuis(rxcuis: list[str], session_id: str | None) -> list[str]:
    # if len(rxcuis) >= 2:
    if len(rxcuis) >= 2:
        # return sorted(set(rxcuis))
        return sorted(set(rxcuis))
    # if not session_id:
    if not session_id:
        # return sorted(set(rxcuis))
        return sorted(set(rxcuis))
    # ctx = await read_context_for_session(session_id)
    ctx = await read_context_for_session(session_id)
    # if not ctx:
    if not ctx:
        # return sorted(set(rxcuis))
        return sorted(set(rxcuis))
    # resolved = {item.rxcui for item in ctx.medications if getattr(item, "rxcui", "")}
    resolved = {item.rxcui for item in ctx.medications if getattr(item, "rxcui", "")}
    # resolved.update(rxcuis)
    resolved.update(rxcuis)
    # return sorted(code for code in resolved if code)
    return sorted(code for code in resolved if code)


# @tool(args_schema=InteractionToolInput)
@tool(args_schema=InteractionToolInput)
# async def check_drug_interaction(rxcuis: list[str], session_id: str | None = None) -> str:
async def check_drug_interaction(rxcuis: list[str], session_id: str | None = None) -> str:
    # """Check RxNorm for known drug-drug interactions for the provided RxCUIs."""
    """Check RxNorm for known drug-drug interactions for the provided RxCUIs."""
    # resolved_rxcuis = await _resolve_rxcuis(rxcuis, session_id)
    resolved_rxcuis = await _resolve_rxcuis(rxcuis, session_id)
    # if len(resolved_rxcuis) < 2:
    if len(resolved_rxcuis) < 2:
        # return dump_tool_result(
        return dump_tool_result(
            # ToolTextResult(
            ToolTextResult(
                # tool_name="check_drug_interaction",
                tool_name="check_drug_interaction",
                # summary="Need at least two RxCUIs or a session with medication RxCUIs to evaluate interactions.",
                summary="Need at least two RxCUIs or a session with medication RxCUIs to evaluate interactions.",
            # )
            )
        # )
        )

    # cache_key = "rxnorm:interact:" + "+".join(sorted(resolved_rxcuis))
    cache_key = "rxnorm:interact:" + "+".join(sorted(resolved_rxcuis))
    # cached = await _cache_get(cache_key)
    cached = await _cache_get(cache_key)
    # if cached:
    if cached:
        # return cached
        return cached

    # url = f"https://rxnav.nlm.nih.gov/REST/interaction/list.json?rxcuis={'+'.join(resolved_rxcuis)}"
    url = f"https://rxnav.nlm.nih.gov/REST/interaction/list.json?rxcuis={'+'.join(resolved_rxcuis)}"
    # async with httpx.AsyncClient(timeout=RXNORM_TIMEOUT_S) as client:
    async with httpx.AsyncClient(timeout=RXNORM_TIMEOUT_S) as client:
        # response = await client.get(url)
        response = await client.get(url)
        # response.raise_for_status()
        response.raise_for_status()
    # data = response.json()
    data = response.json()
    # interactions: list[InteractionRecord] = []
    interactions: list[InteractionRecord] = []
    # for group in data.get("fullInteractionTypeGroup", []):
    for group in data.get("fullInteractionTypeGroup", []):
        # for interaction_type in group.get("fullInteractionType", []):
        for interaction_type in group.get("fullInteractionType", []):
            # for pair in interaction_type.get("interactionPair", []):
            for pair in interaction_type.get("interactionPair", []):
                # interactions.append(
                interactions.append(
                    # InteractionRecord(
                    InteractionRecord(
                        # severity=pair.get("severity", "unknown").upper(),
                        severity=pair.get("severity", "unknown").upper(),
                        # description=pair.get("description", ""),
                        description=pair.get("description", ""),
                    # )
                    )
                # )
                )

    # summary = (
    summary = (
        # "\n".join(f"{item.severity}: {item.description}" for item in interactions)
        "\n".join(f"{item.severity}: {item.description}" for item in interactions)
        # if interactions
        if interactions
        # else "No known interactions found for the provided RxCUIs."
        else "No known interactions found for the provided RxCUIs."
    # )
    )
    # payload = dump_tool_result(
    payload = dump_tool_result(
        # ToolTextResult(
        ToolTextResult(
            # tool_name="check_drug_interaction",
            tool_name="check_drug_interaction",
            # summary=summary,
            summary=summary,
            # data={
            data={
                # "rxcuis": resolved_rxcuis,
                "rxcuis": resolved_rxcuis,
                # "interactions": [item.model_dump(mode="json") for item in interactions],
                "interactions": [item.model_dump(mode="json") for item in interactions],
            # },
            },
        # )
        )
    # )
    )
    # await _cache_set(cache_key, payload)
    await _cache_set(cache_key, payload)
    # return payload
    return payload
