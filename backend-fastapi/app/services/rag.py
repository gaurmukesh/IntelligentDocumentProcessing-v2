"""
RAG Knowledge Base Service — Phase 5

Uses Qdrant (in-memory for local dev) + LangChain + OpenAI embeddings.
Stores admission policies, eligibility rules, board formats, and FAQs.
Retrieves relevant context for eligibility decisions.

Local dev  : Qdrant in-memory (no server required)
UAT / Prod : Qdrant server or Azure AI Search (swap _get_vector_store())
"""

import logging
import os
from pathlib import Path
from typing import Optional

from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

VECTOR_SIZE = 1536    # text-embedding-3-small dimension
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100
TOP_K = 4             # number of chunks to retrieve per query


# ── Qdrant client + vector store ──────────────────────────────────

def _get_qdrant_client() -> QdrantClient:
    """Return Qdrant client — in-memory for local dev."""
    return QdrantClient(path=settings.qdrant_path)


def _get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,
    )


def _get_vector_store() -> QdrantVectorStore:
    client = _get_qdrant_client()

    # Create collection if it doesn't exist
    existing = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection_name not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

    return QdrantVectorStore(
        client=client,
        collection_name=settings.qdrant_collection_name,
        embedding=_get_embeddings(),
    )


# ── Knowledge base ingestion ──────────────────────────────────────

def ingest_knowledge_base(knowledge_base_dir: Optional[str] = None) -> int:
    """
    Load all .txt files from the knowledge base directory,
    chunk them, embed, and store in Qdrant.

    Returns the number of chunks ingested.
    """
    kb_dir = Path(knowledge_base_dir or "data/knowledge_base")
    if not kb_dir.exists():
        logger.warning(f"Knowledge base directory not found: {kb_dir}")
        return 0

    txt_files = list(kb_dir.glob("*.txt"))
    if not txt_files:
        logger.warning(f"No .txt files found in {kb_dir}")
        return 0

    # Load documents
    raw_docs = []
    for filepath in txt_files:
        text = filepath.read_text(encoding="utf-8")
        raw_docs.append(Document(
            page_content=text,
            metadata={"source": filepath.name, "topic": filepath.stem},
        ))
        logger.info(f"Loaded: {filepath.name} ({len(text)} chars)")

    # Chunk documents
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " "],
    )
    chunks = splitter.split_documents(raw_docs)
    logger.info(f"Split into {len(chunks)} chunks")

    # Store in Qdrant
    vector_store = _get_vector_store()
    vector_store.add_documents(chunks)
    logger.info(f"Ingested {len(chunks)} chunks into Qdrant collection '{settings.qdrant_collection_name}'")

    return len(chunks)


def is_knowledge_base_populated() -> bool:
    """Check if the Qdrant collection already has documents."""
    try:
        client = _get_qdrant_client()
        existing = [c.name for c in client.get_collections().collections]
        if settings.qdrant_collection_name not in existing:
            return False
        count = client.count(settings.qdrant_collection_name).count
        return count > 0
    except Exception:
        return False


# ── RAG query ─────────────────────────────────────────────────────

def query_knowledge_base(query: str) -> list[Document]:
    """Retrieve top-k relevant chunks for a given query."""
    vector_store = _get_vector_store()
    results = vector_store.similarity_search(query, k=TOP_K)
    return results


# ── Eligibility check via RAG + GPT-4o ───────────────────────────

openai_client = OpenAI(api_key=settings.openai_api_key)

ELIGIBILITY_SYSTEM_PROMPT = """You are an admission eligibility expert for Indian educational institutions.
Based on the provided admission policies and the student's academic profile, determine if the student is eligible.
Be concise and factual. Always cite the specific rule from the policy that applies.
Respond in JSON format only."""

ELIGIBILITY_USER_PROMPT = """
ADMISSION POLICIES:
{context}

STUDENT PROFILE:
- Course Applied: {course}
- 10th Percentage: {pct_10th}%
- 12th Percentage: {pct_12th}%
- 12th Stream: {stream}
- 12th Result: {result_12th}

Based on the above policies, determine eligibility and respond with:
{{
  "eligible": true/false,
  "reason": "<specific reason citing the policy>",
  "confidence": 0.0-1.0,
  "applicable_rule": "<exact rule from the policy that was applied>"
}}
"""


def check_eligibility(
    course: str,
    pct_10th: Optional[float],
    pct_12th: Optional[float],
    stream: Optional[str],
    result_12th: Optional[str],
) -> dict:
    """
    Run RAG-based eligibility check for a student.

    Returns:
        {
            "eligible": bool,
            "reason": str,
            "confidence": float,
            "applicable_rule": str,
            "context_used": [str],   # chunks retrieved from KB
        }
    """
    import json

    # Build query from student profile
    query = (
        f"Eligibility requirements for {course}. "
        f"Student has {pct_12th}% in 12th grade {stream} stream. "
        f"10th percentage: {pct_10th}%."
    )

    # Retrieve relevant policy chunks
    relevant_docs = query_knowledge_base(query)
    context = "\n\n---\n\n".join([d.page_content for d in relevant_docs])
    context_sources = [d.metadata.get("source", "unknown") for d in relevant_docs]

    # Ask GPT-4o for eligibility decision
    prompt = ELIGIBILITY_USER_PROMPT.format(
        context=context,
        course=course or "Not specified",
        pct_10th=pct_10th or "Not available",
        pct_12th=pct_12th or "Not available",
        stream=stream or "Not specified",
        result_12th=result_12th or "Not available",
    )

    try:
        response = openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": ELIGIBILITY_SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=500,
        )
        result = json.loads(response.choices[0].message.content)
        result["context_used"] = context_sources
        return result

    except Exception as e:
        logger.error(f"Eligibility check failed: {e}")
        return {
            "eligible": None,
            "reason": f"Eligibility check could not be completed: {str(e)}",
            "confidence": 0.0,
            "applicable_rule": "N/A",
            "context_used": context_sources,
        }
