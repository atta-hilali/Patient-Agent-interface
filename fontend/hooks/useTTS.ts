// import { useEffect, useRef } from 'react'
import { useEffect, useRef } from 'react'

// type TTSOptions = {
type TTSOptions = {
  // voiceName?: string
  voiceName?: string
  // rate?: number
  rate?: number
  // pitch?: number
  pitch?: number
// }
}

// export function useTTS(options: TTSOptions = {}) {
export function useTTS(options: TTSOptions = {}) {
  // // Buffer raw tokens until we see sentence boundaries, then speak sentences in order.
  // Buffer raw tokens until we see sentence boundaries, then speak sentences in order.
  // const bufferRef = useRef('')
  const bufferRef = useRef('')
  // const queueRef = useRef<string[]>([])
  const queueRef = useRef<string[]>([])
  // const speakingRef = useRef(false)
  const speakingRef = useRef(false)

  // const speakNext = () => {
  const speakNext = () => {
    // if (speakingRef.current) return
    if (speakingRef.current) return
    // const next = queueRef.current.shift()
    const next = queueRef.current.shift()
    // if (!next) return
    if (!next) return

    // const utterance = new SpeechSynthesisUtterance(next)
    const utterance = new SpeechSynthesisUtterance(next)
    // utterance.rate = options.rate ?? 1
    utterance.rate = options.rate ?? 1
    // utterance.pitch = options.pitch ?? 1
    utterance.pitch = options.pitch ?? 1

    // // Voice lookup is optional because browser voice inventories vary a lot.
    // Voice lookup is optional because browser voice inventories vary a lot.
    // if (options.voiceName) {
    if (options.voiceName) {
      // const match = window.speechSynthesis.getVoices().find((voice) => voice.name === options.voiceName)
      const match = window.speechSynthesis.getVoices().find((voice) => voice.name === options.voiceName)
      // if (match) utterance.voice = match
      if (match) utterance.voice = match
    // }
    }

    // speakingRef.current = true
    speakingRef.current = true
    // utterance.onend = () => {
    utterance.onend = () => {
      // speakingRef.current = false
      speakingRef.current = false
      // speakNext()
      speakNext()
    // }
    }
    // utterance.onerror = () => {
    utterance.onerror = () => {
      // speakingRef.current = false
      speakingRef.current = false
      // speakNext()
      speakNext()
    // }
    }

    // window.speechSynthesis.speak(utterance)
    window.speechSynthesis.speak(utterance)
  // }
  }

  // const enqueue = (sentence: string) => {
  const enqueue = (sentence: string) => {
    // const trimmed = sentence.trim()
    const trimmed = sentence.trim()
    // if (!trimmed) return
    if (!trimmed) return
    // queueRef.current.push(trimmed)
    queueRef.current.push(trimmed)
    // speakNext()
    speakNext()
  // }
  }

  // const onToken = (token: string) => {
  const onToken = (token: string) => {
    // // This regex is intentionally simple: it favors fast MVP playback over perfect sentence parsing.
    // This regex is intentionally simple: it favors fast MVP playback over perfect sentence parsing.
    // bufferRef.current += token
    bufferRef.current += token
    // const sentences = bufferRef.current.match(/[^.!?]+[.!?]+/g)
    const sentences = bufferRef.current.match(/[^.!?]+[.!?]+/g)
    // if (!sentences || sentences.length === 0) return
    if (!sentences || sentences.length === 0) return
    // sentences.forEach(enqueue)
    sentences.forEach(enqueue)
    // bufferRef.current = bufferRef.current.replace(sentences.join(''), '')
    bufferRef.current = bufferRef.current.replace(sentences.join(''), '')
  // }
  }

  // const flush = () => {
  const flush = () => {
    // // Flush any trailing text when the stream ends without punctuation.
    // Flush any trailing text when the stream ends without punctuation.
    // if (bufferRef.current.trim()) {
    if (bufferRef.current.trim()) {
      // enqueue(bufferRef.current)
      enqueue(bufferRef.current)
      // bufferRef.current = ''
      bufferRef.current = ''
    // }
    }
  // }
  }

  // const stop = () => {
  const stop = () => {
    // // Cancel both queued and currently speaking browser utterances.
    // Cancel both queued and currently speaking browser utterances.
    // queueRef.current = []
    queueRef.current = []
    // bufferRef.current = ''
    bufferRef.current = ''
    // speakingRef.current = false
    speakingRef.current = false
    // window.speechSynthesis.cancel()
    window.speechSynthesis.cancel()
  // }
  }

  // useEffect(() => stop, [])
  useEffect(() => stop, [])

  // return { onToken, flush, stop, speak: enqueue }
  return { onToken, flush, stop, speak: enqueue }
// }
}
