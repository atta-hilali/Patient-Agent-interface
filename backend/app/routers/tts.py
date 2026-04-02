# app/routers/tts.py
# Proxies to Magpie Multilingual TTS NIM on GPU 3.
from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel
import httpx

router  = APIRouter()
TTS_URL = 'http://localhost:8000/v1/tts'  # Magpie NIM port

class TTSRequest(BaseModel):
    text:  str
    voice: str = 'en-US-female-1'

@router.post('/tts/synthesize')
async def synthesize(body: TTSRequest):
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(TTS_URL, json={'text':body.text,'voice':body.voice})
    return Response(content=r.content, media_type='audio/wav')
