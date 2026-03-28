import { useEffect, useRef, useState } from 'react'
import { removeBackground } from '../services/api'
import ProgressStatus from './ProgressStatus'

const MAX_FILE_SIZE = 10 * 1024 * 1024
const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/webp']
const UPLOAD_PROGRESS_LABELS = { uploading: '上傳圖片中...', processing: '移除背景中...' }

export default function ImageUploader({ visible = true }) {
  const [file, setFile] = useState(null)
  const [originalUrl, setOriginalUrl] = useState(null)
  const [resultUrl, setResultUrl] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [phase, setPhase] = useState(null)
  const [isDragOver, setIsDragOver] = useState(false)

  const abortControllerRef = useRef(null)
  const phaseTimerRef = useRef(null)
  const dragCounterRef = useRef(0)
  const applyFileRef = useRef(null)

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort()
      clearTimeout(phaseTimerRef.current)
    }
  }, [])

  // Abort in-flight requests and reset loading state when tab becomes hidden
  useEffect(() => {
    if (visible) return
    abortControllerRef.current?.abort()
    clearTimeout(phaseTimerRef.current)
    setLoading(false)
    setPhase(null)
    dragCounterRef.current = 0
    setIsDragOver(false)
  }, [visible])

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

  function applyFile(selected) {
    if (loading) return
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

  applyFileRef.current = applyFile

  function handleFileChange(e) {
    applyFile(e.target.files?.[0] ?? null)
  }

  function handleDragLeave() {
    dragCounterRef.current = Math.max(0, dragCounterRef.current - 1)
    if (dragCounterRef.current === 0) setIsDragOver(false)
  }

  function handleDrop(e) {
    e.preventDefault()
    dragCounterRef.current = 0
    setIsDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) applyFile(dropped)
  }

  // Paste listener — only active when this tab is visible
  useEffect(() => {
    if (!visible) return
    function handlePaste(e) {
      const items = e.clipboardData?.items
      if (!items) return
      for (const item of items) {
        if (item.kind === 'file' && ALLOWED_TYPES.includes(item.type)) {
          e.preventDefault()
          applyFileRef.current(item.getAsFile())
          return
        }
      }
    }
    window.addEventListener('paste', handlePaste)
    return () => window.removeEventListener('paste', handlePaste)
  }, [visible])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!file) return

    abortControllerRef.current?.abort()
    const localController = new AbortController()
    abortControllerRef.current = localController
    setLoading(true)
    setError('')
    setResultUrl(null)
    clearTimeout(phaseTimerRef.current)
    setPhase('uploading')

    const localPhaseTimer = setTimeout(() => setPhase('processing'), 800)
    phaseTimerRef.current = localPhaseTimer
    try {
      const { url } = await removeBackground(file, localController.signal)
      clearTimeout(localPhaseTimer)
      if (localController.signal.aborted) {
        URL.revokeObjectURL(url)
        return
      }
      setPhase('done')
      phaseTimerRef.current = setTimeout(() => setPhase(null), 500)
      setResultUrl(url)
    } catch (err) {
      clearTimeout(localPhaseTimer)
      if (err.name === 'AbortError') return
      if (!localController.signal.aborted) {
        setPhase(null)
        setError(err.message || 'Something went wrong. Please try again.')
      }
    } finally {
      if (!localController.signal.aborted) {
        setLoading(false)
      }
    }
  }

  return (
    <div
      className={`uploader${isDragOver ? ' drag-over' : ''}`}
      onDragEnter={(e) => {
        e.preventDefault()
        if (!Array.from(e.dataTransfer?.types ?? []).includes('Files')) return
        dragCounterRef.current++
        setIsDragOver(true)
      }}
      onDragOver={(e) => {
        if (Array.from(e.dataTransfer?.types ?? []).includes('Files')) e.preventDefault()
      }}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
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
        <ProgressStatus phase={phase} labels={UPLOAD_PROGRESS_LABELS} />
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
