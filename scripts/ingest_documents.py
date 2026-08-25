"""
Sehat Saathi - Document Ingestion Script
==========================================
One-time script to build the RAG vector store from health documents.

Usage:
    python scripts/ingest_documents.py
    python scripts/ingest_documents.py --rebuild   # Force rebuild

Place documents (PDF, TXT, MD) in data/knowledge_base/ before running.
"""
import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Ingest documents into Sehat Saathi RAG vector store")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force rebuild the vector store even if it already exists",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Sehat Saathi - Document Ingestion")
    logger.info("=" * 60)

    from app.config import settings
    logger.info("Knowledge base path: %s", settings.docs_path)
    logger.info("Vector store path: %s", settings.vector_db_path)

    from app.rag.document_loader import load_documents, chunk_documents
    logger.info("Loading documents...")
    docs = load_documents(settings.docs_path)
    logger.info("Loaded %d documents.", len(docs))

    logger.info("Chunking documents...")
    chunks = chunk_documents(docs)
    logger.info("Created %d chunks.", len(chunks))

    logger.info("Building vector store (this may take a minute)...")
    from app.rag.vector_store import build_vector_store
    store = build_vector_store(force_rebuild=args.rebuild)

    count = store._collection.count()
    logger.info("=" * 60)
    logger.info("✅ Vector store ready. Total chunks indexed: %d", count)
    logger.info("Vector store saved to: %s", settings.vector_db_path)
    logger.info("=" * 60)

    # Quick test retrieval
    logger.info("Running test retrieval...")
    retriever = store.as_retriever(search_kwargs={"k": 2})
    test_results = retriever.get_relevant_documents("fever management in children")
    logger.info("Test query 'fever in children' returned %d results.", len(test_results))
    for i, doc in enumerate(test_results, 1):
        logger.info("  Result %d: %s... [source: %s]",
                    i, doc.page_content[:80], doc.metadata.get("source", "unknown"))

    logger.info("✅ Ingestion complete!")


if __name__ == "__main__":
    main()
