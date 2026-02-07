"""Entry point for the PDF RAG server."""

import uvicorn

from pdf_llm_server.server import app


def main():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
