import type { SourceResponse } from '../lib/types'
import { PdfPageViewer } from './PdfPageViewer'

interface EvidenceCardProps {
  source: SourceResponse
  index: number
  isExpanded: boolean
  onToggle: () => void
}

function shortFileName(filePath: string): string {
  const parts = filePath.split('/')
  return parts[parts.length - 1] || filePath
}

export function EvidenceCard({
  source,
  index,
  isExpanded,
  onToggle,
}: EvidenceCardProps) {
  return (
    <div
      className={`border rounded-lg transition-colors ${
        isExpanded
          ? 'border-yellow-300 bg-yellow-50/50'
          : 'border-gray-200 bg-white hover:border-gray-300'
      }`}
    >
      <button
        onClick={onToggle}
        className="w-full text-left px-3 py-2.5 flex items-start gap-2"
      >
        <svg
          className={`h-4 w-4 mt-0.5 shrink-0 text-gray-400 transition-transform ${
            isExpanded ? 'rotate-90' : ''
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5l7 7-7 7"
          />
        </svg>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-xs">
            <span className="inline-flex items-center rounded bg-gray-100 px-1.5 py-0.5 font-medium text-gray-600">
              [{index + 1}]
            </span>
            {source.page_number && (
              <span className="text-gray-500">
                Page {source.page_number}
              </span>
            )}
            <span className="text-gray-400 truncate">
              {shortFileName(source.file_path)}
            </span>
          </div>
          <p className="mt-1 text-xs text-gray-600 line-clamp-2 leading-relaxed">
            {source.content_preview}
          </p>
        </div>
      </button>

      {isExpanded && (
        <div className="border-t border-gray-200 p-3 space-y-3">
          <div className="text-xs text-gray-700 leading-relaxed max-h-32 overflow-y-auto whitespace-pre-wrap">
            {source.content}
          </div>

          {source.page_number && source.document_id && (
            <div className="rounded-lg overflow-hidden border border-gray-200">
              <PdfPageViewer
                documentId={source.document_id}
                pageNumber={source.page_number}
                bbox={source.bbox}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
