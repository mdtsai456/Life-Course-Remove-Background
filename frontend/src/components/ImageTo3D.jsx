import { useEffect, useRef, useState } from 'react'
import { removeBackground, convertTo3D } from '../services/api'

const MAX_FILE_SIZE = 10 * 1024 * 1024
const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/webp']

export default function ImageTo3D() {
  const [file, setFile] = useState(null)
  const [originalUrl, setOriginalUrl] = useState(null)
  const [removedBgUrl, setRemovedBgUrl] = useState(null)
  const [removedBgBlob, setRemovedBgBlob] = useState(null)
  const [model3dUrl, setModel3dUrl] = useState(null)
  const [step, setStep] = useState('idle') // idle | removing | removed | converting | done
  const [error, setError] = useState('')

  const abortControllerRef = useRef(null)

  // Cleanup on unmount: abort pending requests
  useEffect(() => {
    return () => abortControllerRef.current?.abort()
  }, [])

  // Original image preview URL lifecycle
  useEffect(() => {
    if (!file) {
      setOriginalUrl(null)
      return
    }
    const url = URL.createObjectURL(file)
    setOriginalUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  // Removed BG preview URL lifecycle
  useEffect(() => {
    return () => {
      if (removedBgUrl) URL.revokeObjectURL(removedBgUrl)
    }
  }, [removedBgUrl])

  // 3D model URL lifecycle
  useEffect(() => {
    return () => {
      if (model3dUrl) URL.revokeObjectURL(model3dUrl)
    }
  }, [model3dUrl])

  function handleFileChange(e) {
    const selected = e.target.files?.[0] || null
    setError('')
    setRemovedBgUrl(null)
    setRemovedBgBlob(null)
    setModel3dUrl(null)
    setStep('idle')

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

  async function handleRemoveBg(e) {
    e.preventDefault()
    if (!file) return

    abortControllerRef.current?.abort()
    abortControllerRef.current = new AbortController()
    setStep('removing')
    setError('')
    setRemovedBgUrl(null)
    setRemovedBgBlob(null)
    setModel3dUrl(null)

    try {
      const url = await removeBackground(file, abortControllerRef.current.signal)
      // Also store as Blob for re-upload to /api/image-to-3d
      const response = await fetch(url)
      const blob = await response.blob()
      setRemovedBgUrl(url)
      setRemovedBgBlob(blob)
      setStep('removed')
    } catch (err) {
      if (err.name === 'AbortError') return
      setError(err.message || 'Something went wrong. Please try again.')
      setStep('idle')
    }
  }

  async function handleConvertTo3D() {
    if (!removedBgBlob) return

    abortControllerRef.current?.abort()
    abortControllerRef.current = new AbortController()
    setStep('converting')
    setError('')
    setModel3dUrl(null)

    const pngFile = new File([removedBgBlob], 'removed_bg.png', { type: 'image/png' })

    try {
      const url = await convertTo3D(pngFile, abortControllerRef.current.signal)
      setModel3dUrl(url)
      setStep('done')
    } catch (err) {
      if (err.name === 'AbortError') return
      setError(err.message || 'Something went wrong. Please try again.')
      setStep('removed') // 回到 removed 狀態，保留去背結果
    }
  }

  const isRemoving = step === 'removing'
  const isConverting = step === 'converting'
  const showRemovedResult = step === 'removed' || step === 'converting' || step === 'done'
  const show3dResult = step === 'done'

  return (
    <div className="uploader">
      <form className="upload-form" onSubmit={handleRemoveBg}>
        <label htmlFor="img3d-upload" className="file-label">
          <input
            id="img3d-upload"
            type="file"
            accept="image/png, image/jpeg, image/webp"
            onChange={handleFileChange}
            disabled={isRemoving || isConverting}
            className="file-input"
          />
          <span className="file-button">Choose Image</span>
          <span className="file-name">
            {file ? file.name : 'No file chosen'}
          </span>
        </label>
        <button
          type="submit"
          disabled={!file || isRemoving || isConverting}
          className="submit-button"
        >
          {isRemoving ? (
            <span className="spinner-wrapper">
              <span className="spinner" />
              Removing Background…
            </span>
          ) : (
            'Remove Background'
          )}
        </button>
      </form>

      {error && <p className="error-message">{error}</p>}

      {(originalUrl || showRemovedResult) && (
        <div className="preview-grid">
          {originalUrl && (
            <div className="preview-card">
              <h3 className="preview-title">Original</h3>
              <img src={originalUrl} alt="Original" className="preview-image" />
            </div>
          )}
          {showRemovedResult && removedBgUrl && (
            <div className="preview-card">
              <h3 className="preview-title">Background Removed</h3>
              <img
                src={removedBgUrl}
                alt="Background removed"
                className="preview-image checkerboard"
              />
              <a
                href={removedBgUrl}
                download={file ? file.name.replace(/\.[^.]+$/, '') + '_no_bg.png' : 'no_bg.png'}
                className="download-button"
              >
                Download PNG
              </a>
              <button
                onClick={handleConvertTo3D}
                disabled={isConverting}
                className="submit-button"
              >
                {isConverting ? (
                  <span className="spinner-wrapper">
                    <span className="spinner" />
                    Converting to 3D…
                  </span>
                ) : (
                  'Convert to 3D'
                )}
              </button>
            </div>
          )}
        </div>
      )}

      {show3dResult && model3dUrl && (
        <div className="preview-card model-viewer-card">
          <h3 className="preview-title">3D Model</h3>
          {/* eslint-disable-next-line react/no-unknown-property */}
          <model-viewer
            src={model3dUrl}
            auto-rotate
            camera-controls
            className="model-viewer"
          />
          <a
            href={model3dUrl}
            download={file ? file.name.replace(/\.[^.]+$/, '') + '.glb' : 'model.glb'}
            className="download-button"
          >
            Download GLB
          </a>
        </div>
      )}
    </div>
  )
}
