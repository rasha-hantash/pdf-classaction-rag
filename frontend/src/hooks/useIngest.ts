import { useState, useCallback } from 'react'
import { ingestFile } from '../lib/api'
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

      for (const file of Array.from(files)) {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
          setError(`${file.name} is not a PDF file`)
          continue
        }
        if (file.size > 50 * 1024 * 1024) {
          setError(`${file.name} exceeds 50MB limit`)
          continue
        }

        setUploadingFileName(file.name)
        try {
          const result = await ingestFile(file)
          if (result.was_duplicate) {
            setError(`${file.name} was already uploaded`)
          } else if (result.document_id) {
            onDocUploaded({
              id: result.document_id,
              name: file.name,
              chunks: result.chunks_count,
            })
          }
        } catch (e) {
          setError(e instanceof Error ? e.message : 'Upload failed')
        }
      }

      setUploadingFileName(null)
      setIsUploading(false)
    },
    [onDocUploaded],
  )

  const clearError = useCallback(() => setError(null), [])

  return { uploadFiles, isUploading, uploadingFileName, error, clearError }
}
