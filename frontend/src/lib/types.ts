export interface IngestResponse {
  document_id: string | null
  file_path: string
  chunks_count: number
  was_duplicate: boolean
}

export interface SourceResponse {
  chunk_id: string | null
  document_id: string | null
  file_path: string
  page_number: number | null
  content: string
  content_preview: string
  bbox: [number, number, number, number] | null
}

export interface QueryResponse {
  answer: string
  sources: SourceResponse[]
  chunks_used: number
}

export interface BatchIngestItemResponse {
  file_name: string
  document_id: string | null
  chunks_count: number
  was_duplicate: boolean
  error: string | null
}

export interface BatchIngestResponse {
  results: BatchIngestItemResponse[]
  successful: number
  duplicates: number
  failed: number
}

export interface DocumentResponse {
  id: string
  file_path: string
  chunks_count: number
  created_at: string
}

export interface UploadedDoc {
  id: string
  name: string
  chunks: number
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: SourceResponse[]
}
