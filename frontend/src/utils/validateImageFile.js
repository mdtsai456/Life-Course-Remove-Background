import { MAX_FILE_SIZE, ALLOWED_IMAGE_TYPES } from '../constants'

/**
 * Validate an image File against allowed type and size constraints.
 * @param {File} file
 * @returns {{ error: string } | null} null if valid; { error } with user-facing message otherwise
 */
export function validateImageFile(file) {
  if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
    const names = ALLOWED_IMAGE_TYPES.map(t => t.split('/')[1].toUpperCase())
    return { error: `不支援的檔案類型，請上傳 ${names.join('、')} 圖片。` }
  }
  if (file.size > MAX_FILE_SIZE) {
    return { error: `檔案過大，最大允許 ${MAX_FILE_SIZE / (1024 * 1024)} MB。` }
  }
  return null
}
