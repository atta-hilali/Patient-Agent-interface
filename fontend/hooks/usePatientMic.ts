// import { useEffect, useRef, useState } from 'react'
import { useEffect, useRef, useState } from 'react'

// type SpeechRecognitionLike = {
type SpeechRecognitionLike = {
  // continuous: boolean
  continuous: boolean
  // interimResults: boolean
  interimResults: boolean
  // lang: string
  lang: string
  // onresult: ((event: {
  onresult: ((event: {
    // results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal?: boolean }>
    results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal?: boolean }>
  // }) => void) | null
  }) => void) | null
  // onerror: ((event: { error?: string }) => void) | null
  onerror: ((event: { error?: string }) => void) | null
  // start: () => void
  start: () => void
  // stop: () => void
  stop: () => void
// }
}

// type MicOptions = {
type MicOptions = {
  // sessionId: string
  sessionId: string
  // wsBaseUrl?: string
  wsBaseUrl?: string
  // mode?: 'websocket' | 'webspeech'
  mode?: 'websocket' | 'webspeech'
  // onTranscript?: (text: string, isFinal: boolean) => void
  onTranscript?: (text: string, isFinal: boolean) => void
  // onError?: (message: string) => void
  onError?: (message: string) => void
// }
}

// function downsampleTo16kHz(input: Float32Array, inputRate: number): Int16Array {
function downsampleTo16kHz(input: Float32Array, inputRate: number): Int16Array {
  // // The backend expects 16 kHz mono PCM. Most browsers capture at a higher rate,
  // The backend expects 16 kHz mono PCM. Most browsers capture at a higher rate,
  // // so we average samples down before converting to signed 16-bit integers.
  // so we average samples down before converting to signed 16-bit integers.
  // if (inputRate === 16000) {
  if (inputRate === 16000) {
    // const direct = new Int16Array(input.length)
    const direct = new Int16Array(input.length)
    // for (let i = 0; i < input.length; i += 1) {
    for (let i = 0; i < input.length; i += 1) {
      // const sample = Math.max(-1, Math.min(1, input[i]))
      const sample = Math.max(-1, Math.min(1, input[i]))
      // direct[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
      direct[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
    // }
    }
    // return direct
    return direct
  // }
  }

  // const ratio = inputRate / 16000
  const ratio = inputRate / 16000
  // const length = Math.max(1, Math.round(input.length / ratio))
  const length = Math.max(1, Math.round(input.length / ratio))
  // const output = new Int16Array(length)
  const output = new Int16Array(length)
  // let offset = 0
  let offset = 0

  // for (let i = 0; i < length; i += 1) {
  for (let i = 0; i < length; i += 1) {
    // const next = Math.min(input.length, Math.round((i + 1) * ratio))
    const next = Math.min(input.length, Math.round((i + 1) * ratio))
    // let sum = 0
    let sum = 0
    // let count = 0
    let count = 0
    // while (offset < next) {
    while (offset < next) {
      // sum += input[offset]
      sum += input[offset]
      // offset += 1
      offset += 1
      // count += 1
      count += 1
    // }
    }
    // const sample = Math.max(-1, Math.min(1, count ? sum / count : 0))
    const sample = Math.max(-1, Math.min(1, count ? sum / count : 0))
    // output[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
    output[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
  // }
  }

  // return output
  return output
// }
}

// export function usePatientMic({
export function usePatientMic({
  // sessionId,
  sessionId,
  // wsBaseUrl,
  wsBaseUrl,
  // mode = 'websocket',
  mode = 'websocket',
  // onTranscript,
  onTranscript,
  // onError,
  onError,
// }: MicOptions) {
}: MicOptions) {
  // // Keep long-lived media and transport objects in refs so they can be torn down safely.
  // Keep long-lived media and transport objects in refs so they can be torn down safely.
  // const wsRef = useRef<WebSocket | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  // const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  // const streamRef = useRef<MediaStream | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  // const audioContextRef = useRef<AudioContext | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  // const processorRef = useRef<ScriptProcessorNode | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  // const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  // const [isRecording, setIsRecording] = useState(false)
  const [isRecording, setIsRecording] = useState(false)

  // const stop = () => {
  const stop = () => {
    // recognitionRef.current?.stop()
    recognitionRef.current?.stop()
    // processorRef.current?.disconnect()
    processorRef.current?.disconnect()
    // sourceRef.current?.disconnect()
    sourceRef.current?.disconnect()
    // streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current?.getTracks().forEach((track) => track.stop())
    // audioContextRef.current?.close()
    audioContextRef.current?.close()
    // if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) {
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) {
      // wsRef.current.close()
      wsRef.current.close()
    // }
    }
    // recognitionRef.current = null
    recognitionRef.current = null
    // processorRef.current = null
    processorRef.current = null
    // sourceRef.current = null
    sourceRef.current = null
    // streamRef.current = null
    streamRef.current = null
    // audioContextRef.current = null
    audioContextRef.current = null
    // wsRef.current = null
    wsRef.current = null
    // setIsRecording(false)
    setIsRecording(false)
  // }
  }

  // const start = async () => {
  const start = async () => {
    // if (!sessionId) {
    if (!sessionId) {
      // onError?.('Missing session id for microphone streaming.')
      onError?.('Missing session id for microphone streaming.')
      // return
      return
    // }
    }

    // if (mode === 'webspeech') {
    if (mode === 'webspeech') {
      // const speechWindow = window as Window & {
      const speechWindow = window as Window & {
        // SpeechRecognition?: new () => SpeechRecognitionLike
        SpeechRecognition?: new () => SpeechRecognitionLike
        // webkitSpeechRecognition?: new () => SpeechRecognitionLike
        webkitSpeechRecognition?: new () => SpeechRecognitionLike
      // }
      }
      // const SpeechRecognitionCtor = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition
      const SpeechRecognitionCtor = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition
      // if (!SpeechRecognitionCtor) {
      if (!SpeechRecognitionCtor) {
        // onError?.('Browser speech recognition is only available in Chrome or Edge.')
        onError?.('Browser speech recognition is only available in Chrome or Edge.')
        // return
        return
      // }
      }

      // const recognition = new SpeechRecognitionCtor()
      const recognition = new SpeechRecognitionCtor()
      // recognition.lang = 'en-US'
      recognition.lang = 'en-US'
      // recognition.continuous = true
      recognition.continuous = true
      // recognition.interimResults = true
      recognition.interimResults = true
      // recognition.onresult = (event) => {
      recognition.onresult = (event) => {
        // const lastResult = event.results[event.results.length - 1]
        const lastResult = event.results[event.results.length - 1]
        // const transcript = lastResult?.[0]?.transcript ?? ''
        const transcript = lastResult?.[0]?.transcript ?? ''
        // if (!transcript) return
        if (!transcript) return
        // onTranscript?.(transcript, Boolean(lastResult?.isFinal))
        onTranscript?.(transcript, Boolean(lastResult?.isFinal))
      // }
      }
      // recognition.onerror = (event) => onError?.(event.error || 'Speech recognition failed.')
      recognition.onerror = (event) => onError?.(event.error || 'Speech recognition failed.')
      // recognition.start()
      recognition.start()
      // recognitionRef.current = recognition
      recognitionRef.current = recognition
      // setIsRecording(true)
      setIsRecording(true)
      // return
      return
    // }
    }

    // try {
    try {
      // // Production path: capture mono PCM and stream it to the backend websocket.
      // Production path: capture mono PCM and stream it to the backend websocket.
      // const stream = await navigator.mediaDevices.getUserMedia({
      const stream = await navigator.mediaDevices.getUserMedia({
        // audio: {
        audio: {
          // channelCount: 1,
          channelCount: 1,
          // echoCancellation: true,
          echoCancellation: true,
          // noiseSuppression: true,
          noiseSuppression: true,
        // },
        },
      // })
      })
      // streamRef.current = stream
      streamRef.current = stream

      // const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      // const base = wsBaseUrl ?? `${protocol}://${window.location.host}`
      const base = wsBaseUrl ?? `${protocol}://${window.location.host}`
      // const ws = new WebSocket(`${base.replace(/^http/, 'ws')}/ws/audio/${sessionId}`)
      const ws = new WebSocket(`${base.replace(/^http/, 'ws')}/ws/audio/${sessionId}`)
      // ws.binaryType = 'arraybuffer'
      ws.binaryType = 'arraybuffer'
      // ws.onmessage = (event) => {
      ws.onmessage = (event) => {
        // const data = JSON.parse(event.data) as { type?: string; text?: string }
        const data = JSON.parse(event.data) as { type?: string; text?: string }
        // if (!data.text) return
        if (!data.text) return
        // onTranscript?.(data.text, data.type === 'transcript_final')
        onTranscript?.(data.text, data.type === 'transcript_final')
      // }
      }
      // ws.onerror = () => onError?.('Microphone websocket connection failed.')
      ws.onerror = () => onError?.('Microphone websocket connection failed.')
      // wsRef.current = ws
      wsRef.current = ws

      // const audioContext = new AudioContext()
      const audioContext = new AudioContext()
      // audioContextRef.current = audioContext
      audioContextRef.current = audioContext
      // const source = audioContext.createMediaStreamSource(stream)
      const source = audioContext.createMediaStreamSource(stream)
      // sourceRef.current = source
      sourceRef.current = source
      // const processor = audioContext.createScriptProcessor(4096, 1, 1)
      const processor = audioContext.createScriptProcessor(4096, 1, 1)
      // processorRef.current = processor
      processorRef.current = processor

      // processor.onaudioprocess = (event) => {
      processor.onaudioprocess = (event) => {
        // if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
        // const input = event.inputBuffer.getChannelData(0)
        const input = event.inputBuffer.getChannelData(0)
        // const pcm16 = downsampleTo16kHz(input, audioContext.sampleRate)
        const pcm16 = downsampleTo16kHz(input, audioContext.sampleRate)
        // wsRef.current.send(pcm16.buffer)
        wsRef.current.send(pcm16.buffer)
      // }
      }

      // source.connect(processor)
      source.connect(processor)
      // processor.connect(audioContext.destination)
      processor.connect(audioContext.destination)
      // setIsRecording(true)
      setIsRecording(true)
    // } catch (error) {
    } catch (error) {
      // stop()
      stop()
      // onError?.(error instanceof Error ? error.message : 'Unable to start microphone capture.')
      onError?.(error instanceof Error ? error.message : 'Unable to start microphone capture.')
    // }
    }
  // }
  }

  // useEffect(() => stop, [])
  useEffect(() => stop, [])

  // return { isRecording, start, stop }
  return { isRecording, start, stop }
// }
}
