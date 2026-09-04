"""
Sehat Saathi — Document Ingestion Script
==========================================
Run this ONCE to load all documents from data/knowledge_base/
into the Chroma vector store at data/vector_store/.

Usage:
    cd sehat-saathi
    python scripts/ingest_documents.py

Run again with --rebuild to force re-ingest all documents:
    python scripts/ingest_documents.py --rebuild
"""
import sys
import os
import argparse
import logging

# Allow running from the sehat-saathi root directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Ingest knowledge base documents into vector store.")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild even if vector store exists.")
    args = parser.parse_args()

    from app.config import settings

    docs_path = settings.docs_path
    vector_db_path = settings.vector_db_path

    logger.info("=" * 60)
    logger.info("Sehat Saathi — Knowledge Base Ingestion")
    logger.info("=" * 60)
    logger.info("Documents path : %s", os.path.abspath(docs_path))
    logger.info("Vector DB path : %s", os.path.abspath(vector_db_path))
    logger.info("Force rebuild  : %s", args.rebuild)
    logger.info("")

    # Check documents exist
    if not os.path.exists(docs_path):
        logger.error("Documents directory not found: %s", docs_path)
        logger.error("Create the directory and add .txt or .pdf files, then re-run.")
        sys.exit(1)

    doc_files = [f for f in os.listdir(docs_path) if f.endswith((".txt", ".pdf", ".md"))]
    if not doc_files:
        logger.warning("No .txt, .pdf, or .md files found in %s", docs_path)
        logger.warning("The RAG will use built-in seed documents only.")
    else:
        logger.info("Found %d document(s) to ingest:", len(doc_files))
        for f in doc_files:
            size_kb = os.path.getsize(os.path.join(docs_path, f)) // 1024
            logger.info("  - %s (%d KB)", f, size_kb)

    logger.info("")
    logger.info("Building vector store...")

    try:
        from app.rag.vector_store import build_vector_store
        store = build_vector_store(force_rebuild=args.rebuild)
        count = store._collection.count()
        logger.info("")
        logger.info("=" * 60)
        logger.info("SUCCESS — Vector store built!")
        logger.info("Total document chunks indexed: %d", count)
        logger.info("Vector store location: %s", os.path.abspath(vector_db_path))
        logger.info("=" * 60)
        logger.info("")
        logger.info("The RAG is ready. Start the backend with:")
        logger.info("  uvicorn app.api.routes:app --reload --port 8000")
    except Exception as e:
        logger.exception("Ingestion failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
