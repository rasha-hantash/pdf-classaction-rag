import { useRef } from 'react'
import type { UploadedDoc } from '../lib/types'

interface DocumentListProps {
  docs: UploadedDoc[]
  isUploading: boolean
  uploadingFileName: string | null
  error: string | null
  onClearError: () => void
  onFilesSelected: (files: FileList) => void
}

export function DocumentList({
  docs,
  isUploading,
  uploadingFileName,
  error,
  onClearError,
  onFilesSelected,
}: DocumentListProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const folderInputRef = useRef<HTMLInputElement>(null)

  const handleClick = () => {
    fileInputRef.current?.click()
  }

  const handleFolderClick = () => {
    folderInputRef.current?.click()
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFilesSelected(e.target.files)
      e.target.value = ''
    }
  }

  const handleFolderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const pdfFiles = Array.from(e.target.files).filter((f) =>
        f.name.toLowerCase().endsWith('.pdf'),
      )
      if (pdfFiles.length > 0) {
        const dt = new DataTransfer()
        for (const file of pdfFiles) {
          dt.items.add(file)
        }
        onFilesSelected(dt.files)
      }
      e.target.value = ''
    }
  }

  return (
    <div className="border-b border-border-warm bg-warm-white px-4 py-3">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        multiple
        className="hidden"
        onChange={handleChange}
      />
      <input
        ref={folderInputRef}
        type="file"
        className="hidden"
        onChange={handleFolderChange}
        {...({ webkitdirectory: '', directory: '' } as React.InputHTMLAttributes<HTMLInputElement>)}
      />

      {docs.length === 0 && !isUploading ? (
        <div className="text-center py-4">
          <p className="text-sm text-stone-500 mb-2">
            Upload PDF documents to get started
          </p>
          <div className="flex gap-2">
            <button
              onClick={handleClick}
              className="inline-flex items-center gap-1.5 rounded-lg bg-terracotta px-3.5 py-2 text-sm font-medium text-white hover:bg-terracotta-hover transition-colors"
            >
              <svg
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              Upload files
            </button>
            <button
              onClick={handleFolderClick}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border-warm px-3.5 py-2 text-sm font-medium text-stone-700 hover:bg-cream transition-colors"
            >
              <svg
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
                />
              </svg>
              Upload folder
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {docs.map((doc) => (
            <span
              key={doc.id}
              className="inline-flex items-center gap-1 rounded-full bg-cream-dark px-2.5 py-1 text-xs text-stone-700"
            >
              <svg
                className="h-3 w-3 text-stone-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
                />
              </svg>
              {doc.name}
              <span className="text-stone-400">({doc.chunks} chunks)</span>
            </span>
          ))}

          {isUploading && uploadingFileName && (
            <span className="inline-flex items-center gap-1 rounded-full bg-terracotta-light px-2.5 py-1 text-xs text-terracotta">
              <svg
                className="h-3 w-3 animate-spin"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              {uploadingFileName}
            </span>
          )}

          <button
            onClick={handleClick}
            disabled={isUploading}
            className="inline-flex items-center gap-1 rounded-full border border-dashed border-border-warm px-2.5 py-1 text-xs text-stone-500 hover:border-border-warm-hover hover:text-stone-600 transition-colors disabled:opacity-50"
          >
            <svg
              className="h-3 w-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 4v16m8-8H4"
              />
            </svg>
            Upload files
          </button>
          <button
            onClick={handleFolderClick}
            disabled={isUploading}
            className="inline-flex items-center gap-1 rounded-full border border-dashed border-border-warm px-2.5 py-1 text-xs text-stone-500 hover:border-border-warm-hover hover:text-stone-600 transition-colors disabled:opacity-50"
          >
            <svg
              className="h-3 w-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
              />
            </svg>
            Upload folder
          </button>
        </div>
      )}

      {error && (
        <div className="mt-2 flex items-center gap-2 text-xs text-red-600">
          <span>{error}</span>
          <button onClick={onClearError} className="underline hover:no-underline">
            dismiss
          </button>
        </div>
      )}
    </div>
  )
}
