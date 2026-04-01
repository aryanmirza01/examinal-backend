"""
ChromaDB vector store — NVIDIA embeddings + reranking integration.
"""

import logging
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings

logger = logging.getLogger(__name__)


class VectorStoreService:
    _client: chromadb.ClientAPI | None = None
    _embedder = None
    _provider: str | None = None

    def __init__(self):
        if VectorStoreService._client is None:
            VectorStoreService._client = chromadb.PersistentClient(
                path=settings.VECTOR_STORE_DIR,
                settings=ChromaSettings(anonymized_telemetry=False),
            )

        if VectorStoreService._embedder is None:
            provider = settings.EMBEDDING_PROVIDER.lower()
            VectorStoreService._provider = provider

            if provider == "nvidia_api":
                from app.services.nvidia_embedder import NvidiaEmbedder
                VectorStoreService._embedder = NvidiaEmbedder()
                logger.info("Embedding: NVIDIA API — %s", settings.NVIDIA_EMBED_MODEL)

            elif provider == "nvidia_local":
                from sentence_transformers import SentenceTransformer
                model_name = settings.NVIDIA_EMBED_MODEL.replace("nvidia/", "")
                VectorStoreService._embedder = SentenceTransformer(model_name, trust_remote_code=True)
                logger.info("Embedding: NVIDIA local — %s", model_name)

            else:
                from sentence_transformers import SentenceTransformer
                VectorStoreService._embedder = SentenceTransformer(settings.EMBEDDING_MODEL)
                logger.info("Embedding: local — %s", settings.EMBEDDING_MODEL)

        self.client = VectorStoreService._client
        self.embedder = VectorStoreService._embedder
        self.provider = VectorStoreService._provider

    def _get_or_create_collection(self, name: str):
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def _embed(self, texts: List[str], input_type: str = "passage") -> List[List[float]]:
        if self.provider == "nvidia_api":
            return self.embedder.embed(texts, input_type=input_type)
        elif self.provider == "nvidia_local":
            embeddings = self.embedder.encode(texts, show_progress_bar=False)
            return embeddings.tolist()
        else:
            embeddings = self.embedder.encode(texts, show_progress_bar=False)
            return embeddings.tolist()

    def _embed_query(self, text: str) -> List[float]:
        if self.provider == "nvidia_api":
            return self.embedder.embed_query(text)
        return self._embed([text], input_type="query")[0]

    def _embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embed(texts, input_type="passage")

    def add_passage(
        self,
        collection_name: str,
        passage_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        collection = self._get_or_create_collection(collection_name)
        embedding = self._embed_documents([text])[0]
        safe_meta = {k: v for k, v in (metadata or {}).items() if v is not None}
        collection.add(
            ids=[passage_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[safe_meta],
        )
        return passage_id

    def add_passages_batch(
        self,
        collection_name: str,
        passage_ids: List[str],
        texts: List[str],
        metadatas: Optional[List[Dict]] = None,
    ):
        collection = self._get_or_create_collection(collection_name)
        embeddings = self._embed_documents(texts)
        collection.add(
            ids=passage_ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas or [{}] * len(texts),
        )
        logger.info("Batch added %d passages to %s", len(texts), collection_name)

    def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        where: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        collection = self._get_or_create_collection(collection_name)
        if collection.count() == 0:
            return []

        query_embedding = self._embed_query(query)
        kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": min(top_k, collection.count()),
        }
        if where:
            kwargs["where"] = where

        results = collection.query(**kwargs)
        output = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                output.append({
                    "id": results["ids"][0][i] if results["ids"] else None,
                    "text": doc,
                    "distance": results["distances"][0][i] if results["distances"] else None,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })
        return output

    def search_with_rerank(
        self,
        collection_name: str,
        query: str,
        initial_top_k: int = 25,
        final_top_k: int = 6,
    ) -> List[Dict[str, Any]]:
        candidates = self.search(collection_name, query, top_k=initial_top_k)
        if not candidates:
            return []

        if settings.USE_RERANKER and settings.NVIDIA_API_KEY:
            try:
                from app.services.nvidia_embedder import NvidiaReranker
                reranker = NvidiaReranker()
                reranked = reranker.rerank(query, candidates, top_k=final_top_k)
                return reranked
            except Exception as e:
                logger.warning("Reranking failed, using embedding results: %s", e)
                return candidates[:final_top_k]
        return candidates[:final_top_k]

    def delete_passages(self, collection_name: str, passage_ids: List[str]):
        try:
            collection = self.client.get_collection(collection_name)
            collection.delete(ids=passage_ids)
        except Exception as e:
            logger.warning("Delete failed from %s: %s", collection_name, e)

    def delete_collection(self, collection_name: str):
        try:
            self.client.delete_collection(collection_name)
        except Exception as e:
            logger.warning("Delete collection %s failed: %s", collection_name, e)

    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        try:
            collection = self.client.get_collection(collection_name)
            return {
                "name": collection_name,
                "count": collection.count(),
                "provider": self.provider,
                "embed_model": settings.NVIDIA_EMBED_MODEL if self.provider and self.provider.startswith("nvidia") else settings.EMBEDDING_MODEL,
                "reranker": settings.NVIDIA_RERANK_MODEL if settings.USE_RERANKER else "disabled",
            }
        except Exception:
            return {"name": collection_name, "count": 0}