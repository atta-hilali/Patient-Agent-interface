# from __future__ import annotations
from __future__ import annotations

# import asyncio
import asyncio
# import queue
import queue
# import threading
import threading
# from dataclasses import dataclass
from dataclasses import dataclass
# from typing import Any
from typing import Any

# import httpx
import httpx

# from app.config import Settings
from app.config import Settings


# @dataclass
@dataclass
# class TranscriptEvent:
class TranscriptEvent:
    # type: str
    type: str
    # text: str
    text: str
    # is_final: bool
    is_final: bool

    # def as_dict(self, session_id: str) -> dict[str, Any]:
    def as_dict(self, session_id: str) -> dict[str, Any]:
        # return {
        return {
            # "type": self.type,
            "type": self.type,
            # "text": self.text,
            "text": self.text,
            # "session_id": session_id,
            "session_id": session_id,
        # }
        }


# class BaseASRSession:
class BaseASRSession:
    # async def receive_audio(self, pcm: bytes) -> list[TranscriptEvent]:
    async def receive_audio(self, pcm: bytes) -> list[TranscriptEvent]:
        # raise NotImplementedError
        raise NotImplementedError

    # async def finish(self) -> list[TranscriptEvent]:
    async def finish(self) -> list[TranscriptEvent]:
        # raise NotImplementedError
        raise NotImplementedError


# class HttpChunkASRSession(BaseASRSession):
class HttpChunkASRSession(BaseASRSession):
    # def __init__(self, endpoint: str, sample_rate_hz: int) -> None:
    def __init__(self, endpoint: str, sample_rate_hz: int) -> None:
        # self.endpoint = endpoint
        self.endpoint = endpoint
        # self.sample_rate_hz = sample_rate_hz
        self.sample_rate_hz = sample_rate_hz
        # self.buffer = bytearray()
        self.buffer = bytearray()
        # # 250 ms of 16 kHz mono 16-bit PCM: 16000 * 2 * 0.25 = 8000 bytes.
        # 250 ms of 16 kHz mono 16-bit PCM: 16000 * 2 * 0.25 = 8000 bytes.
        # self.chunk_bytes = int(sample_rate_hz * 2 * 0.25)
        self.chunk_bytes = int(sample_rate_hz * 2 * 0.25)

    # async def _transcribe(self, audio_bytes: bytes) -> list[TranscriptEvent]:
    async def _transcribe(self, audio_bytes: bytes) -> list[TranscriptEvent]:
        # async with httpx.AsyncClient(timeout=5.0) as client:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # response = await client.post(
            response = await client.post(
                # self.endpoint,
                self.endpoint,
                # content=audio_bytes,
                content=audio_bytes,
                # headers={"Content-Type": "audio/pcm"},
                headers={"Content-Type": "audio/pcm"},
            # )
            )
            # response.raise_for_status()
            response.raise_for_status()
        # data = response.json()
        data = response.json()
        # text = data.get("partial") or data.get("transcript", "")
        text = data.get("partial") or data.get("transcript", "")
        # if not text:
        if not text:
            # return []
            return []
        # is_final = bool(data.get("is_final"))
        is_final = bool(data.get("is_final"))
        # return [
        return [
            # TranscriptEvent(
            TranscriptEvent(
                # type="transcript_final" if is_final else "transcript_partial",
                type="transcript_final" if is_final else "transcript_partial",
                # text=text,
                text=text,
                # is_final=is_final,
                is_final=is_final,
            # )
            )
        # ]
        ]

    # async def receive_audio(self, pcm: bytes) -> list[TranscriptEvent]:
    async def receive_audio(self, pcm: bytes) -> list[TranscriptEvent]:
        # self.buffer.extend(pcm)
        self.buffer.extend(pcm)
        # if len(self.buffer) < self.chunk_bytes:
        if len(self.buffer) < self.chunk_bytes:
            # return []
            return []
        # chunk = bytes(self.buffer)
        chunk = bytes(self.buffer)
        # self.buffer = bytearray()
        self.buffer = bytearray()
        # return await self._transcribe(chunk)
        return await self._transcribe(chunk)

    # async def finish(self) -> list[TranscriptEvent]:
    async def finish(self) -> list[TranscriptEvent]:
        # if not self.buffer:
        if not self.buffer:
            # return []
            return []
        # chunk = bytes(self.buffer)
        chunk = bytes(self.buffer)
        # self.buffer = bytearray()
        self.buffer = bytearray()
        # events = await self._transcribe(chunk)
        events = await self._transcribe(chunk)
        # final_text = next((event.text for event in reversed(events) if event.text), "")
        final_text = next((event.text for event in reversed(events) if event.text), "")
        # if not final_text:
        if not final_text:
            # return []
            return []
        # return [TranscriptEvent(type="transcript_final", text=final_text, is_final=True)]
        return [TranscriptEvent(type="transcript_final", text=final_text, is_final=True)]


# class RivaGrpcASRSession(BaseASRSession):
class RivaGrpcASRSession(BaseASRSession):
    # def __init__(self, settings: Settings) -> None:
    def __init__(self, settings: Settings) -> None:
        # self.settings = settings
        self.settings = settings
        # self._audio_queue: queue.Queue[bytes | None] = queue.Queue()
        self._audio_queue: queue.Queue[bytes | None] = queue.Queue()
        # self._event_queue: queue.Queue[TranscriptEvent] = queue.Queue()
        self._event_queue: queue.Queue[TranscriptEvent] = queue.Queue()
        # self._worker_error: Exception | None = None
        self._worker_error: Exception | None = None
        # self._stop_event = threading.Event()
        self._stop_event = threading.Event()
        # self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread = threading.Thread(target=self._worker, daemon=True)
        # self._thread.start()
        self._thread.start()

    # def _worker(self) -> None:
    def _worker(self) -> None:
        # try:
        try:
            # import riva.client  # type: ignore[import-not-found]
            import riva.client  # type: ignore[import-not-found]
        # except Exception as exc:  # noqa: BLE001
        except Exception as exc:  # noqa: BLE001
            # self._worker_error = RuntimeError(
            self._worker_error = RuntimeError(
                # "VOICE_ASR_MODE=riva_grpc requires the `nvidia-riva-client` package."
                "VOICE_ASR_MODE=riva_grpc requires the `nvidia-riva-client` package."
            # )
            )
            # self._event_queue.put(TranscriptEvent(type="asr_error", text=str(exc), is_final=True))
            self._event_queue.put(TranscriptEvent(type="asr_error", text=str(exc), is_final=True))
            # return
            return

        # try:
        try:
            # auth = riva.client.Auth(uri=self.settings.riva_grpc_target, use_ssl=self.settings.riva_use_ssl)
            auth = riva.client.Auth(uri=self.settings.riva_grpc_target, use_ssl=self.settings.riva_use_ssl)
            # asr_service = riva.client.ASRService(auth)
            asr_service = riva.client.ASRService(auth)
            # recognition_config = riva.client.RecognitionConfig(
            recognition_config = riva.client.RecognitionConfig(
                # encoding=riva.client.AudioEncoding.LINEAR_PCM,
                encoding=riva.client.AudioEncoding.LINEAR_PCM,
                # sample_rate_hertz=self.settings.riva_sample_rate_hz,
                sample_rate_hertz=self.settings.riva_sample_rate_hz,
                # language_code=self.settings.riva_language_code,
                language_code=self.settings.riva_language_code,
                # max_alternatives=1,
                max_alternatives=1,
                # enable_automatic_punctuation=True,
                enable_automatic_punctuation=True,
                # audio_channel_count=1,
                audio_channel_count=1,
                # verbatim_transcripts=False,
                verbatim_transcripts=False,
            # )
            )
            # streaming_config = riva.client.StreamingRecognitionConfig(
            streaming_config = riva.client.StreamingRecognitionConfig(
                # config=recognition_config,
                config=recognition_config,
                # interim_results=True,
                interim_results=True,
            # )
            )

            # def audio_chunks():
            def audio_chunks():
                # while not self._stop_event.is_set():
                while not self._stop_event.is_set():
                    # chunk = self._audio_queue.get()
                    chunk = self._audio_queue.get()
                    # if chunk is None:
                    if chunk is None:
                        # break
                        break
                    # yield chunk
                    yield chunk

            # responses = asr_service.streaming_response_generator(
            responses = asr_service.streaming_response_generator(
                # audio_chunks=audio_chunks(),
                audio_chunks=audio_chunks(),
                # streaming_config=streaming_config,
                streaming_config=streaming_config,
            # )
            )
            # for response in responses:
            for response in responses:
                # for result in getattr(response, "results", []):
                for result in getattr(response, "results", []):
                    # alternatives = getattr(result, "alternatives", [])
                    alternatives = getattr(result, "alternatives", [])
                    # transcript = alternatives[0].transcript if alternatives else ""
                    transcript = alternatives[0].transcript if alternatives else ""
                    # if not transcript:
                    if not transcript:
                        # continue
                        continue
                    # is_final = bool(getattr(result, "is_final", False))
                    is_final = bool(getattr(result, "is_final", False))
                    # self._event_queue.put(
                    self._event_queue.put(
                        # TranscriptEvent(
                        TranscriptEvent(
                            # type="transcript_final" if is_final else "transcript_partial",
                            type="transcript_final" if is_final else "transcript_partial",
                            # text=transcript,
                            text=transcript,
                            # is_final=is_final,
                            is_final=is_final,
                        # )
                        )
                    # )
                    )
        # except Exception as exc:  # noqa: BLE001
        except Exception as exc:  # noqa: BLE001
            # self._worker_error = exc
            self._worker_error = exc
            # self._event_queue.put(TranscriptEvent(type="asr_error", text=str(exc), is_final=True))
            self._event_queue.put(TranscriptEvent(type="asr_error", text=str(exc), is_final=True))

    # async def _drain_events(self) -> list[TranscriptEvent]:
    async def _drain_events(self) -> list[TranscriptEvent]:
        # events: list[TranscriptEvent] = []
        events: list[TranscriptEvent] = []
        # while True:
        while True:
            # try:
            try:
                # events.append(self._event_queue.get_nowait())
                events.append(self._event_queue.get_nowait())
            # except queue.Empty:
            except queue.Empty:
                # break
                break
        # if self._worker_error:
        if self._worker_error:
            # raise RuntimeError(str(self._worker_error)) from self._worker_error
            raise RuntimeError(str(self._worker_error)) from self._worker_error
        # return events
        return events

    # async def receive_audio(self, pcm: bytes) -> list[TranscriptEvent]:
    async def receive_audio(self, pcm: bytes) -> list[TranscriptEvent]:
        # self._audio_queue.put(pcm)
        self._audio_queue.put(pcm)
        # await asyncio.sleep(0)
        await asyncio.sleep(0)
        # return await self._drain_events()
        return await self._drain_events()

    # async def finish(self) -> list[TranscriptEvent]:
    async def finish(self) -> list[TranscriptEvent]:
        # self._stop_event.set()
        self._stop_event.set()
        # self._audio_queue.put(None)
        self._audio_queue.put(None)
        # await asyncio.to_thread(self._thread.join, 1.0)
        await asyncio.to_thread(self._thread.join, 1.0)
        # return await self._drain_events()
        return await self._drain_events()


# def create_asr_session(settings: Settings) -> BaseASRSession:
def create_asr_session(settings: Settings) -> BaseASRSession:
    # if settings.voice_asr_mode == "riva_grpc":
    if settings.voice_asr_mode == "riva_grpc":
        # return RivaGrpcASRSession(settings)
        return RivaGrpcASRSession(settings)
    # return HttpChunkASRSession(
    return HttpChunkASRSession(
        # endpoint=settings.riva_asr_http_url,
        endpoint=settings.riva_asr_http_url,
        # sample_rate_hz=settings.riva_sample_rate_hz,
        sample_rate_hz=settings.riva_sample_rate_hz,
    # )
    )
