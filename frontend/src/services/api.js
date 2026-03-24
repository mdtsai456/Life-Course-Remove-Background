export async function removeBackground(file) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch('/api/remove-background', {
    method: 'POST',
    body: formData,
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
  if (!blob || blob.size === 0) {
    throw new Error('Received empty response from server.')
  }
  return URL.createObjectURL(blob)
}
