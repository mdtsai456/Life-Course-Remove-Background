async function postForBlob(url, formData, fallbackMessage, signal) {
  const response = await fetch(url, {
    method: 'POST',
    body: formData,
    signal,
  })

  if (!response.ok) {
    let message = fallbackMessage
    try {
      const errorData = await response.json()
      if (typeof errorData.detail === 'string') {
        message = errorData.detail
      } else if (Array.isArray(errorData.detail)) {
        message = errorData.detail.map(e => e.msg ?? e.message ?? String(e)).join('; ')
      }
    } catch (err) {
      if (err.name === 'AbortError') throw err
    }
    throw new Error(message)
  }

  const blob = await response.blob()
  if (blob.size === 0) {
    throw new Error('Received empty response from server.')
  }
  return URL.createObjectURL(blob)
}

export async function removeBackground(file, signal) {
  const formData = new FormData()
  formData.append('file', file)
  return postForBlob('/api/remove-background', formData, 'Failed to remove background.', signal)
}

export async function convertTo3D(file, signal) {
  const formData = new FormData()
  formData.append('file', file)
  return postForBlob('/api/image-to-3d', formData, 'Failed to convert to 3D.', signal)
}

export async function cloneVoice(audioFile, text, signal) {
  const formData = new FormData()
  formData.append('file', audioFile)
  formData.append('text', text ?? '')
  return postForBlob('/api/clone-voice', formData, 'Failed to clone voice.', signal)
}
