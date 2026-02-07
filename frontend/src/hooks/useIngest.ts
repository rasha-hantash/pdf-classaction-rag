import { useState, useCallback } from 'react'
import { ingestFile, ingestBatch } from '../lib/api'
import type { UploadedDoc } from '../lib/types'

interface UseIngestReturn {
  uploadFiles: (files: FileList) => Promise<void>
  isUploading: boolean
  uploadingFileName: string | null
  error: string | null
  clearError: () => void
}

export function useIngest(
  onDocUploaded: (doc: UploadedDoc) => void,
): UseIngestReturn {
  const [isUploading, setIsUploading] = useState(false)
  const [uploadingFileName, setUploadingFileName] = useState<string | null>(
    null,
  )
  const [error, setError] = useState<string | null>(null)

  const uploadFiles = useCallback(
    async (files: FileList) => {
      setIsUploading(true)
      setError(null)
      const errors: string[] = []
      const fileArray = Array.from(files)

      // Client-side validation
      const validFiles: File[] = []
      for (const file of fileArray) {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
          errors.push(`${file.name} is not a PDF file`)
          continue
        }
        if (file.size > 50 * 1024 * 1024) {
          errors.push(`${file.name} exceeds 50MB limit`)
          continue
        }
        validFiles.push(file)
      }

      if (validFiles.length > 1) {
        // Batch upload
        setUploadingFileName(`Uploading ${validFiles.length} files...`)
        try {
          const batchResult = await ingestBatch(validFiles)
          for (const item of batchResult.results) {
            if (item.error) {
              errors.push(`${item.file_name}: ${item.error}`)
            } else if (item.was_duplicate) {
              errors.push(`${item.file_name} was already uploaded`)
            } else if (item.document_id) {
              onDocUploaded({
                id: item.document_id,
                name: item.file_name,
                chunks: item.chunks_count,
              })
            }
          }
        } catch (e) {
          errors.push(e instanceof Error ? e.message : 'Batch upload failed')
        }
      } else if (validFiles.length === 1) {
        // Single file upload
        const file = validFiles[0]
        setUploadingFileName(file.name)
        try {
          const result = await ingestFile(file)
          if (result.was_duplicate) {
            errors.push(`${file.name} was already uploaded`)
          } else if (result.document_id) {
            onDocUploaded({
              id: result.document_id,
              name: file.name,
              chunks: result.chunks_count,
            })
          }
        } catch (e) {
          errors.push(e instanceof Error ? e.message : `${file.name} upload failed`)
        }
      }

      if (errors.length > 0) {
        setError(errors.join('; '))
      }

      setUploadingFileName(null)
      setIsUploading(false)
    },
    [onDocUploaded],
  )

  const clearError = useCallback(() => setError(null), [])

  return { uploadFiles, isUploading, uploadingFileName, error, clearError }
}
