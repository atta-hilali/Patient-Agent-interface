from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import httpx

from app.config import get_settings

router = APIRouter()

class TTSRequest(BaseModel):
    text: str
    voice: str = "en-US-female-1"

@router.post("/tts/synthesize")
async def synthesize(body: TTSRequest):
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(settings.tts_nim_url, json={"text": body.text, "voice": body.voice})
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        raise HTTPException(status_code=502, detail=f"TTS upstream error: {detail}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"TTS request failed: {exc}") from exc

    return Response(content=response.content, media_type="audio/wav")
