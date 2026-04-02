# from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
# from starlette.websockets import WebSocketState
from starlette.websockets import WebSocketState

# from app.audio_asr import create_asr_session
from app.audio_asr import create_asr_session
# from app.config import get_settings
from app.config import get_settings

# router = APIRouter()
router = APIRouter()


# @router.websocket("/ws/audio/{session_id}")
@router.websocket("/ws/audio/{session_id}")
# async def audio_ws(ws: WebSocket, session_id: str):
async def audio_ws(ws: WebSocket, session_id: str):
    # await ws.accept()
    await ws.accept()
    # session = create_asr_session(get_settings())
    session = create_asr_session(get_settings())
    # try:
    try:
        # while True:
        while True:
            # pcm = await ws.receive_bytes()
            pcm = await ws.receive_bytes()
            # events = await session.receive_audio(pcm)
            events = await session.receive_audio(pcm)
            # for event in events:
            for event in events:
                # await ws.send_json(event.as_dict(session_id))
                await ws.send_json(event.as_dict(session_id))
    # except WebSocketDisconnect:
    except WebSocketDisconnect:
        # return
        return
    # except Exception as exc:  # noqa: BLE001
    except Exception as exc:  # noqa: BLE001
        # await ws.send_json({"type": "asr_error", "text": str(exc), "session_id": session_id})
        await ws.send_json({"type": "asr_error", "text": str(exc), "session_id": session_id})
        # await ws.close()
        await ws.close()
    # finally:
    finally:
        # try:
        try:
            # events = await session.finish()
            events = await session.finish()
            # for event in events:
            for event in events:
                # if ws.client_state == WebSocketState.CONNECTED:
                if ws.client_state == WebSocketState.CONNECTED:
                    # await ws.send_json(event.as_dict(session_id))
                    await ws.send_json(event.as_dict(session_id))
        # except Exception:
        except Exception:
            # pass
            pass
