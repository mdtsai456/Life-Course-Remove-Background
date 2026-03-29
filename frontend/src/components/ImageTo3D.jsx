import { useEffect, useState } from 'react'
import { removeBackground, convertTo3D } from '../services/api'
import { IMAGE_ACCEPT_STRING } from '../constants'
import { validateImageFile } from '../utils/validateImageFile'
import { revokeResultUrl } from '../utils/revokeResultUrl'
import useAsyncSubmit from '../hooks/useAsyncSubmit'
import { useDerivedObjectUrl, useManagedObjectUrl } from '../hooks/useObjectUrl'
import LoadingButton from './LoadingButton'
import ProgressStatus from './ProgressStatus'

const REMOVE_BG_PROGRESS_LABELS = { uploading: '上傳圖片中...', processing: '移除背景中...' }
const CONVERT_3D_PROGRESS_LABELS = { uploading: '上傳圖片中...', processing: '轉換 3D 中...' }

export default function ImageTo3D({ visible = true }) {
  const [file, setFile] = useState(null)
  const originalUrl = useDerivedObjectUrl(file)
  const [removedBgUrl, setRemovedBgUrl] = useManagedObjectUrl()
  const [removedBgBlob, setRemovedBgBlob] = useState(null)
  const [model3dUrl, setModel3dUrl] = useManagedObjectUrl()
  const [step, setStep] = useState('idle') // idle | removing | removed | converting | done
  const [error, setError] = useState('')

  const removeOp = useAsyncSubmit()
  const convertOp = useAsyncSubmit()

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      removeOp.reset()
      convertOp.reset()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset is stable (useCallback)
  }, [removeOp.reset, convertOp.reset])

  // Abort in-flight requests and reset loading state when tab becomes hidden
  useEffect(() => {
    if (visible) return
    removeOp.reset()
    convertOp.reset()
    setError('')
    setFile(null)
    setRemovedBgUrl(null)
    setRemovedBgBlob(null)
    setModel3dUrl(null)
    setStep('idle')
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset is stable (useCallback)
  }, [visible, removeOp.reset, convertOp.reset])

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

    const validation = validateImageFile(selected)
    if (validation) {
      setError(validation.error)
      setFile(null)
      return
    }

    setFile(selected)
  }

  async function handleRemoveBg(e) {
    e.preventDefault()
    if (!file) return

    setStep('removing')
    setError('')
    setRemovedBgUrl(null)
    setRemovedBgBlob(null)
    setModel3dUrl(null)

    removeOp.execute(
      (signal) => removeBackground(file, signal),
      {
        onSuccess: (result) => {
          setRemovedBgUrl(result.url)
          setRemovedBgBlob(result.blob)
          setStep('removed')
        },
        onError: (err) => {
          setError(err.message || '發生錯誤，請重試。')
          setStep('idle')
        },
        onAbortCleanup: revokeResultUrl,
      },
    )
  }

  async function handleConvertTo3D() {
    if (!removedBgBlob) return

    setStep('converting')
    setError('')
    setModel3dUrl(null)

    const pngFile = new File([removedBgBlob], 'removed_bg.png', { type: 'image/png' })

    convertOp.execute(
      (signal) => convertTo3D(pngFile, signal),
      {
        onSuccess: (result) => {
          setModel3dUrl(result.url)
          setStep('done')
        },
        onError: (err) => {
          setError(err.message || '發生錯誤，請重試。')
          setStep('removed')
        },
        onAbortCleanup: revokeResultUrl,
      },
    )
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
            accept={IMAGE_ACCEPT_STRING}
            onChange={handleFileChange}
            disabled={isRemoving || isConverting}
            className="file-input"
          />
          <span className="file-button">Choose Image</span>
          <span className="file-name">
            {file ? file.name : 'No file chosen'}
          </span>
        </label>
        <LoadingButton
          type="submit"
          disabled={!file || isRemoving || isConverting}
          className="submit-button"
          loading={isRemoving}
          loadingText="Removing Background…"
        >
          Remove Background
        </LoadingButton>
        <ProgressStatus phase={removeOp.phase} labels={REMOVE_BG_PROGRESS_LABELS} />
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
              <LoadingButton
                onClick={handleConvertTo3D}
                disabled={isConverting}
                className="submit-button"
                loading={isConverting}
                loadingText="Converting to 3D…"
              >
                Convert to 3D
              </LoadingButton>
              <ProgressStatus phase={convertOp.phase} labels={CONVERT_3D_PROGRESS_LABELS} />
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
