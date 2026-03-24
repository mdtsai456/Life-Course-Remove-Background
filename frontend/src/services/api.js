export async function removeBackground(file, signal) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch('/api/remove-background', {
    method: 'POST',
    body: formData,
    signal,
  })

  if (!response.ok) {
    let message = 'Failed to remove background.'
    try {
      const errorData = await response.json()
      message = errorData.detail || message
    } catch {
      // ignore JSON parse failure
    }
    throw new Error(message)
  }

  const blob = await response.blob()
  if (blob.size === 0) {
    throw new Error('Received empty response from server.')
  }
  return URL.createObjectURL(blob)
}

export async function convertTo3D(file, signal) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch('/api/image-to-3d', {
    method: 'POST',
    body: formData,
    signal,
  })

  if (!response.ok) {
    let message = 'Failed to convert to 3D.'
    try {
      const errorData = await response.json()
      message = errorData.detail || message
    } catch {
      // ignore JSON parse failure
    }
    throw new Error(message)
  }

  const blob = await response.blob()
  if (blob.size === 0) {
    throw new Error('Received empty response from server.')
  }
  return URL.createObjectURL(blob)
}

export async function cloneVoice(audioFile, text, signal) {
  const formData = new FormData()
  formData.append('file', audioFile)
  formData.append('text', text)

  const response = await fetch('/api/clone-voice', {
    method: 'POST',
    body: formData,
    signal,
  })

  if (!response.ok) {
    let message = 'Failed to clone voice.'
    try {
      const errorData = await response.json()
      if (typeof errorData.detail === 'string') {
        message = errorData.detail
      } else if (Array.isArray(errorData.detail)) {
        message = errorData.detail.map(e => e.msg).join('; ')
      }
    } catch {
      // ignore JSON parse failure
    }
    throw new Error(message)
  }

  const blob = await response.blob()
  if (blob.size === 0) {
    throw new Error('Received empty response from server.')
  }
  return URL.createObjectURL(blob)
}
