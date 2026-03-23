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

  const data = await response.json()
  const imageUrl = typeof data.url === 'string' ? data.url.trim() : ''
  if (!imageUrl) {
    throw new Error(`Invalid API response: expected a non-empty url string but got: ${JSON.stringify(data.url)}`)
  }
  return imageUrl
}
