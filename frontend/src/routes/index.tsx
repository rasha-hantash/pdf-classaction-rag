import { useState, useCallback, useEffect } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { ChatPanel, EvidencePanel } from '../components'
import { useIngest, useRagQuery } from '../hooks'
import { listDocuments } from '../lib/api'
import type { Message, UploadedDoc, SourceResponse } from '../lib/types'

export const Route = createFileRoute('/')({
  component: Home,
})

function Home() {
  const [messages, setMessages] = useState<Message[]>([])
  const [docs, setDocs] = useState<UploadedDoc[]>([])
  const [currentSources, setCurrentSources] = useState<SourceResponse[]>([])
  const [showEvidence, setShowEvidence] = useState(false)

  // Load existing documents on mount
  useEffect(() => {
    listDocuments().then((existing) => {
      setDocs(
        existing.map((d) => ({
          id: d.id,
          name: d.file_path.split('/').pop() || d.file_path,
          chunks: d.chunks_count,
        })),
      )
    }).catch(() => {
      // Backend might not be running yet — ignore
    })
  }, [])

  const handleDocUploaded = useCallback((doc: UploadedDoc) => {
    setDocs((prev) => [...prev, doc])
  }, [])

  const { uploadFiles, isUploading, uploadingFileName, error: uploadError, clearError } =
    useIngest(handleDocUploaded)

  const { submitQuery, isQuerying } = useRagQuery()

  const handleSubmitQuery = useCallback(
    async (question: string) => {
      setMessages((prev) => [...prev, { role: 'user', content: question }])
      setCurrentSources([])

      const response = await submitQuery(question)

      if (response) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: response.answer,
            sources: response.sources,
          },
        ])
        setCurrentSources(response.sources)
        if (response.sources.length > 0) {
          setShowEvidence(true)
        }
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: 'Sorry, something went wrong. Please try again.',
          },
        ])
      }
    },
    [submitQuery],
  )

  return (
    <div className="flex h-screen">
      <div
        className={`transition-all duration-300 ease-in-out ${
          showEvidence ? 'w-1/2' : 'w-full'
        }`}
      >
        <ChatPanel
          messages={messages}
          docs={docs}
          isUploading={isUploading}
          uploadingFileName={uploadingFileName}
          uploadError={uploadError}
          isQuerying={isQuerying}
          onClearUploadError={clearError}
          onFilesSelected={uploadFiles}
          onSubmitQuery={handleSubmitQuery}
        />
      </div>

      {showEvidence && (
        <div className="w-1/2 transition-all duration-300 ease-in-out">
          <EvidencePanel sources={currentSources} isLoading={isQuerying} />
        </div>
      )}
    </div>
  )
}
