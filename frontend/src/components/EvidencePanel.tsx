import { useState } from 'react'
import type { SourceResponse } from '../lib/types'
import { EvidenceCard } from './EvidenceCard'

interface EvidencePanelProps {
  sources: SourceResponse[]
  isLoading: boolean
}

export function EvidencePanel({ sources, isLoading }: EvidencePanelProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null)

  const handleToggle = (index: number) => {
    setExpandedIndex((prev) => (prev === index ? null : index))
  }

  return (
    <div className="flex h-full flex-col border-l border-gray-200 bg-gray-50">
      <div className="border-b border-gray-200 bg-white px-4 py-3">
        <h2 className="text-sm font-medium text-gray-700">
          Sources
          {sources.length > 0 && (
            <span className="ml-1.5 text-gray-400">({sources.length})</span>
          )}
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {isLoading && (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="animate-pulse rounded-lg border border-gray-200 bg-white p-3"
              >
                <div className="h-3 w-24 rounded bg-gray-200 mb-2" />
                <div className="h-3 w-full rounded bg-gray-100" />
                <div className="h-3 w-2/3 rounded bg-gray-100 mt-1" />
              </div>
            ))}
          </div>
        )}

        {!isLoading && sources.length === 0 && (
          <div className="flex items-center justify-center h-32 text-sm text-gray-400">
            No evidence for this query
          </div>
        )}

        {!isLoading &&
          sources.map((source, i) => (
            <EvidenceCard
              key={source.chunk_id ?? i}
              source={source}
              index={i}
              isExpanded={expandedIndex === i}
              onToggle={() => handleToggle(i)}
            />
          ))}
      </div>
    </div>
  )
}
