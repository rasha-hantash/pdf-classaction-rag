import type { IngestResponse, QueryResponse, DocumentResponse } from './types'

export async function ingestFile(file: File): Promise<IngestResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch('/api/v1/rag/ingest', {
    method: 'POST',
    body: formData,
  })

  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail ?? `Upload failed (${res.status})`)
  }

  return res.json()
}

export async function queryRag(
  question: string,
  topK = 5,
): Promise<QueryResponse> {
  const res = await fetch('/api/v1/rag/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, top_k: topK }),
  })

  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail ?? `Query failed (${res.status})`)
  }

  return res.json()
}

export async function listDocuments(): Promise<DocumentResponse[]> {
  const res = await fetch('/api/v1/documents')
  if (!res.ok) {
    throw new Error(`Failed to list documents (${res.status})`)
  }
  return res.json()
}

export function getPdfFileUrl(documentId: string): string {
  return `/api/v1/documents/${documentId}/file`
}
