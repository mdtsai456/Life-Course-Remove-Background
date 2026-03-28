import { useEffect, useRef, useState } from 'react'
import { removeBackground, convertTo3D } from '../services/api'
import ProgressStatus from './ProgressStatus'

const MAX_FILE_SIZE = 10 * 1024 * 1024
const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/webp']

export default function ImageTo3D({ visible = true }) {
  const [file, setFile] = useState(null)
  const [originalUrl, setOriginalUrl] = useState(null)
  const [removedBgUrl, setRemovedBgUrl] = useState(null)
  const [removedBgBlob, setRemovedBgBlob] = useState(null)
  const [model3dUrl, setModel3dUrl] = useState(null)
  const [step, setStep] = useState('idle') // idle | removing | removed | converting | done
  const [error, setError] = useState('')
  const [removePhase, setRemovePhase] = useState(null)
  const [convertPhase, setConvertPhase] = useState(null)

  const abortControllerRef = useRef(null)
  const removePhaseTimerRef = useRef(null)
  const convertPhaseTimerRef = useRef(null)
  const uploadTimerRef = useRef(null)

  // Cleanup on unmount: abort pending requests
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort()
      clearTimeout(removePhaseTimerRef.current)
      clearTimeout(convertPhaseTimerRef.current)
      clearTimeout(uploadTimerRef.current)
    }
  }, [])

  // Abort in-flight requests and reset loading state when tab becomes hidden
  useEffect(() => {
    if (visible) return
    abortControllerRef.current?.abort()
    clearTimeout(removePhaseTimerRef.current)
    clearTimeout(convertPhaseTimerRef.current)
    clearTimeout(uploadTimerRef.current)
    setRemovePhase(null)
    setConvertPhase(null)
    // Reset step from loading states while preserving completed results
    setStep(prev => {
      if (prev === 'removing') return 'idle'
      if (prev === 'converting') return 'removed'
      return prev
    })
  }, [visible])

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
    const localController = new AbortController()
    abortControllerRef.current = localController
    setStep('removing')
    setError('')
    setRemovedBgUrl(null)
    setRemovedBgBlob(null)
    setModel3dUrl(null)
    clearTimeout(removePhaseTimerRef.current)
    setRemovePhase('uploading')

    const localUploadTimer = setTimeout(() => setRemovePhase('processing'), 800)
    uploadTimerRef.current = localUploadTimer
    let url
    try {
      const result = await removeBackground(file, localController.signal)
      url = result.url
      clearTimeout(localUploadTimer)
      if (localController.signal.aborted) {
        if (url) URL.revokeObjectURL(url)
        return
      }
      setRemovePhase('done')
      removePhaseTimerRef.current = setTimeout(() => setRemovePhase(null), 500)
      setRemovedBgUrl(url)
      setRemovedBgBlob(result.blob)
      setStep('removed')
    } catch (err) {
      clearTimeout(localUploadTimer)
      if (url) URL.revokeObjectURL(url)
      if (err.name === 'AbortError' || localController.signal.aborted) return
      setRemovePhase(null)
      setError(err.message || 'Something went wrong. Please try again.')
      setStep('idle')
    }
  }

  async function handleConvertTo3D() {
    if (!removedBgBlob) return

    abortControllerRef.current?.abort()
    const localController = new AbortController()
    abortControllerRef.current = localController
    setStep('converting')
    setError('')
    setModel3dUrl(null)
    clearTimeout(convertPhaseTimerRef.current)
    setConvertPhase('uploading')

    const pngFile = new File([removedBgBlob], 'removed_bg.png', { type: 'image/png' })

    const localUploadTimer = setTimeout(() => setConvertPhase('processing'), 800)
    uploadTimerRef.current = localUploadTimer
    let url
    try {
      ;({ url } = await convertTo3D(pngFile, localController.signal))
      clearTimeout(localUploadTimer)
      if (localController.signal.aborted) {
        if (url) URL.revokeObjectURL(url)
        return
      }
      setConvertPhase('done')
      convertPhaseTimerRef.current = setTimeout(() => setConvertPhase(null), 500)
      setModel3dUrl(url)
      setStep('done')
    } catch (err) {
      clearTimeout(localUploadTimer)
      if (url) URL.revokeObjectURL(url)
      if (err.name === 'AbortError' || localController.signal.aborted) return
      setConvertPhase(null)
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
        <ProgressStatus phase={removePhase} labels={{ uploading: '上傳圖片中...', processing: '移除背景中...' }} />
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
              <ProgressStatus phase={convertPhase} labels={{ uploading: '上傳圖片中...', processing: '轉換 3D 中...' }} />
            </div>
          )}
        </div>
      )}

      {show3dResult && model3dUrl && (
        <div className="preview-card model-viewer-card">
          <h3 className="preview-title">3D Model</h3>
          <model-viewer
            src={model3dUrl}
            auto-rotate
            camera-controls
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
