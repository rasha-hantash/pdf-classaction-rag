ALTER TABLE documents ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'processing';
ALTER TABLE documents ADD COLUMN file_size BIGINT;

-- Backfill existing documents as processed
UPDATE documents SET status = 'processed';
