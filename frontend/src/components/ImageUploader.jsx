import { useEffect, useRef, useState } from 'react'
import { removeBackground } from '../services/api'

const MAX_FILE_SIZE = 10 * 1024 * 1024
const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/webp']

export default function ImageUploader() {
  const [file, setFile] = useState(null)
  const [originalUrl, setOriginalUrl] = useState(null)
  const [resultUrl, setResultUrl] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const abortControllerRef = useRef(null)

  useEffect(() => {
    return () => abortControllerRef.current?.abort()
  }, [])

  useEffect(() => {
    if (!file) {
      setOriginalUrl(null)
      return
    }
    const url = URL.createObjectURL(file)
    setOriginalUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  useEffect(() => {
    return () => {
      if (resultUrl) URL.revokeObjectURL(resultUrl)
    }
  }, [resultUrl])

  function handleFileChange(e) {
    const selected = e.target.files?.[0] || null
    setError('')
    setResultUrl(null)

    if (!selected) {
      setFile(null)
      return
    }

    if (!ALLOWED_TYPES.includes(selected.type)) {
      setError('Unsupported file type. Please upload a PNG, JPEG, or WebP image.')
      setFile(null)
      return
    }

    if (selected.size > MAX_FILE_SIZE) {
      setError('File is too large. Maximum allowed size is 10 MB.')
      setFile(null)
      return
    }

    setFile(selected)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!file) return

    abortControllerRef.current = new AbortController()
    setLoading(true)
    setError('')
    setResultUrl(null)

    try {
      const url = await removeBackground(file, abortControllerRef.current.signal)
      setResultUrl(url)
    } catch (err) {
      if (err.name === 'AbortError') return
      setError(err.message || 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="uploader">
      <form className="upload-form" onSubmit={handleSubmit}>
        <label htmlFor="image-upload" className="file-label">
          <input
            id="image-upload"
            type="file"
            accept="image/png, image/jpeg, image/webp"
            onChange={handleFileChange}
            disabled={loading}
            className="file-input"
          />
          <span className="file-button">Choose Image</span>
          <span className="file-name">
            {file ? file.name : 'No file chosen'}
          </span>
        </label>
        <button
          type="submit"
          disabled={!file || loading}
          className="submit-button"
        >
          {loading ? (
            <span className="spinner-wrapper">
              <span className="spinner" />
              Processing…
            </span>
          ) : (
            'Remove Background'
          )}
        </button>
      </form>

      {error && <p className="error-message">{error}</p>}

      {(originalUrl || resultUrl) && (
        <div className="preview-grid">
          {originalUrl && (
            <div className="preview-card">
              <h3 className="preview-title">Original</h3>
              <img src={originalUrl} alt="Original" className="preview-image" />
            </div>
          )}
          {resultUrl && (
            <div className="preview-card">
              <h3 className="preview-title">Result</h3>
              <img src={resultUrl} alt="Background removed" className="preview-image checkerboard" />
              <a
                href={resultUrl}
                download={file ? file.name.replace(/\.[^.]+$/, '') + '_no_bg.png' : 'background-removed.png'}
                className="download-button"
              >
                Download
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
