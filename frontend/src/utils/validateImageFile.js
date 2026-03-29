import { MAX_FILE_SIZE, ALLOWED_IMAGE_TYPES } from '../constants'

/**
 * Validate an image File against allowed type and size constraints.
 * @param {File} file
 * @returns {{ error: string } | null} null if valid; { error } with user-facing message otherwise
 */
export function validateImageFile(file) {
  if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
    return { error: '不支援的檔案類型，請上傳 PNG、JPEG 或 WebP 圖片。' }
  }
  if (file.size > MAX_FILE_SIZE) {
    return { error: '檔案過大，最大允許 10 MB。' }
  }
  return null
}
