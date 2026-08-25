"""
Sehat Saathi - RAG Vector Store
================================
Sets up and manages the Chroma vector database for RAG retrieval.
Uses sentence-transformers for embeddings (no additional API key required)
or watsonx embeddings if configured.

On first run: loads documents, chunks them, embeds, and persists to disk.
On subsequent runs: loads the persisted Chroma DB for fast retrieval.
"""
import logging
import os
from pathlib import Path
from typing import Optional

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.schema import Document

from app.config import settings
from app.rag.document_loader import load_documents, chunk_documents

logger = logging.getLogger(__name__)

# Embedding model — runs locally, no API key needed
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Chroma collection name
COLLECTION_NAME = "sehat_saathi_health_kb"

_vector_store: Optional[Chroma] = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    """Initialize embedding model."""
    logger.info("Loading embedding model: %s", EMBEDDING_MODEL)
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def build_vector_store(force_rebuild: bool = False) -> Chroma:
    """
    Build or load the Chroma vector store.

    Args:
        force_rebuild: If True, re-ingest all documents even if store exists.

    Returns:
        Initialized Chroma vector store.
    """
    global _vector_store

    if _vector_store is not None and not force_rebuild:
        return _vector_store

    vector_db_path = settings.vector_db_path
    embeddings = _get_embeddings()

    # Check if a persisted store already exists
    if os.path.exists(vector_db_path) and os.listdir(vector_db_path) and not force_rebuild:
        logger.info("Loading existing vector store from: %s", vector_db_path)
        _vector_store = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=vector_db_path,
        )
        count = _vector_store._collection.count()
        logger.info("Vector store loaded. Document chunks: %d", count)
        return _vector_store

    # Build from scratch
    logger.info("Building vector store from documents in: %s", settings.docs_path)
    docs = load_documents(settings.docs_path)
    chunks = chunk_documents(docs)

    if not chunks:
        logger.warning("No documents found. Creating empty vector store.")
        chunks = [Document(page_content="Sehat Saathi health knowledge base.", metadata={"source": "seed"})]

    Path(vector_db_path).mkdir(parents=True, exist_ok=True)

    _vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=vector_db_path,
    )
    _vector_store.persist()
    logger.info(
        "Vector store built and persisted. Total chunks: %d", len(chunks)
    )
    return _vector_store


def get_retriever(k: int = 4):
    """
    Get a retriever from the vector store.

    Args:
        k: Number of documents to retrieve per query.

    Returns:
        LangChain retriever.
    """
    store = build_vector_store()
    return store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )


def get_vector_store() -> Chroma:
    """Return the singleton vector store, building if necessary."""
    return build_vector_store()
