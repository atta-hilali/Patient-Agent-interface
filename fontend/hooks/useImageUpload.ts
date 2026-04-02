// import { useState } from 'react'
import { useState } from 'react'

// export function useImageUpload() {
export function useImageUpload() {
  // const [pendingImageB64, setPendingImageB64] = useState<string | null>(null)
  const [pendingImageB64, setPendingImageB64] = useState<string | null>(null)
  // const [pendingFileName, setPendingFileName] = useState<string | null>(null)
  const [pendingFileName, setPendingFileName] = useState<string | null>(null)

  // const encode = (file: File): Promise<string> =>
  const encode = (file: File): Promise<string> =>
    // new Promise((resolve, reject) => {
    new Promise((resolve, reject) => {
      // // Resize before encoding so image uploads stay lightweight enough for the
      // Resize before encoding so image uploads stay lightweight enough for the
      // // "attach to next message" flow and the multimodal analyzer.
      // "attach to next message" flow and the multimodal analyzer.
      // const canvas = document.createElement('canvas')
      const canvas = document.createElement('canvas')
      // const img = new Image()
      const img = new Image()
      // img.onload = () => {
      img.onload = () => {
        // const max = 1024
        const max = 1024
        // const ratio = Math.min(max / img.width, max / img.height, 1)
        const ratio = Math.min(max / img.width, max / img.height, 1)
        // canvas.width = Math.round(img.width * ratio)
        canvas.width = Math.round(img.width * ratio)
        // canvas.height = Math.round(img.height * ratio)
        canvas.height = Math.round(img.height * ratio)
        // const ctx = canvas.getContext('2d')
        const ctx = canvas.getContext('2d')
        // if (!ctx) {
        if (!ctx) {
          // reject(new Error('Could not create canvas context for image encoding.'))
          reject(new Error('Could not create canvas context for image encoding.'))
          // return
          return
        // }
        }
        // ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
        // const b64 = canvas.toDataURL('image/jpeg', 0.85).split(',')[1]
        const b64 = canvas.toDataURL('image/jpeg', 0.85).split(',')[1]
        // URL.revokeObjectURL(img.src)
        URL.revokeObjectURL(img.src)
        // resolve(b64)
        resolve(b64)
      // }
      }
      // img.onerror = () => reject(new Error('Selected file could not be loaded as an image.'))
      img.onerror = () => reject(new Error('Selected file could not be loaded as an image.'))
      // img.src = URL.createObjectURL(file)
      img.src = URL.createObjectURL(file)
    // })
    })

  // const attachNextImage = async (file: File) => {
  const attachNextImage = async (file: File) => {
    // // Keep the encoded image in local state until the next chat submit merges it
    // Keep the encoded image in local state until the next chat submit merges it
    // // into the same `(message, image_b64)` payload as a normal text turn.
    // into the same `(message, image_b64)` payload as a normal text turn.
    // const b64 = await encode(file)
    const b64 = await encode(file)
    // setPendingImageB64(b64)
    setPendingImageB64(b64)
    // setPendingFileName(file.name)
    setPendingFileName(file.name)
    // return b64
    return b64
  // }
  }

  // const consumeImage = () => {
  const consumeImage = () => {
    // const image_b64 = pendingImageB64
    const image_b64 = pendingImageB64
    // setPendingImageB64(null)
    setPendingImageB64(null)
    // setPendingFileName(null)
    setPendingFileName(null)
    // return image_b64
    return image_b64
  // }
  }

  // const clearImage = () => {
  const clearImage = () => {
    // setPendingImageB64(null)
    setPendingImageB64(null)
    // setPendingFileName(null)
    setPendingFileName(null)
  // }
  }

  // const buildMultipartPayload = (message: string, sessionId: string, modality = 'image') => {
  const buildMultipartPayload = (message: string, sessionId: string, modality = 'image') => {
    // const formData = new FormData()
    const formData = new FormData()
    // formData.append('session_id', sessionId)
    formData.append('session_id', sessionId)
    // formData.append('message', message)
    formData.append('message', message)
    // formData.append('modality', modality)
    formData.append('modality', modality)
    // if (pendingImageB64) {
    if (pendingImageB64) {
      // formData.append('image_b64', pendingImageB64)
      formData.append('image_b64', pendingImageB64)
    // }
    }
    // if (pendingFileName) {
    if (pendingFileName) {
      // formData.append('image_name', pendingFileName)
      formData.append('image_name', pendingFileName)
    // }
    }
    // return formData
    return formData
  // }
  }

  // return {
  return {
    // pendingImageB64,
    pendingImageB64,
    // pendingFileName,
    pendingFileName,
    // encode,
    encode,
    // attachNextImage,
    attachNextImage,
    // consumeImage,
    consumeImage,
    // clearImage,
    clearImage,
    // buildMultipartPayload,
    buildMultipartPayload,
  // }
  }
// }
}
