"""
NVIDIA NIM clients: Embedder + Reranker + LLM.
"""

import logging
import time
import requests
from typing import List, Optional, Dict, Any

from app.config import settings

logger = logging.getLogger(__name__)


class NvidiaLLM:
    """
    NVIDIA NIM LLM client.
    Model: nvidia/nemotron-3-nano-30b-a3b
    """

    def __init__(self):
        self.api_key = settings.NVIDIA_API_KEY
        self.base_url = settings.NVIDIA_BASE_URL.rstrip("/")
        self.model = settings.NVIDIA_LLM_MODEL
        logger.info("NvidiaLLM initialized: %s", self.model)

    def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        from openai import OpenAI

        client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE,
            "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        start = time.perf_counter()
        try:
            response = client.chat.completions.create(**kwargs)
            elapsed = time.perf_counter() - start
            result = response.choices[0].message.content or ""
            logger.info(
                "NVIDIA LLM: %d chars in %.2fs (model=%s, tokens=%d)",
                len(result), elapsed, self.model,
                max_tokens or settings.LLM_MAX_TOKENS,
            )
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start
            logger.error("NVIDIA LLM failed after %.2fs: %s", elapsed, str(e))
            raise

    def chat_with_retry(self, prompt: str, system_prompt: str = "", retries: int = 2, **kwargs) -> str:
        last_error = None
        for attempt in range(retries + 1):
            try:
                return self.chat(prompt, system_prompt, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < retries:
                    wait = 2 ** attempt
                    logger.warning("NVIDIA LLM attempt %d failed, retry in %ds: %s", attempt + 1, wait, str(e))
                    time.sleep(wait)
        raise last_error


class NvidiaEmbedder:
    """
    NVIDIA NIM embedding client.
    Model: nvidia/llama-3.2-nv-embedqa-1b-v2
    """

    def __init__(self):
        self.api_key = settings.NVIDIA_API_KEY
        self.base_url = settings.NVIDIA_BASE_URL.rstrip("/")
        self.model = settings.NVIDIA_EMBED_MODEL
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        self._dimension: Optional[int] = None
        logger.info("NvidiaEmbedder initialized: %s", self.model)

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            test = self.embed(["dimension test"])
            self._dimension = len(test[0])
            logger.info("Embedding dimension: %d", self._dimension)
        return self._dimension

    def embed(self, texts: List[str], input_type: str = "passage") -> List[List[float]]:
        if not texts:
            return []

        url = f"{self.base_url}/embeddings"
        all_embeddings = []
        batch_size = 50

        for i in range(0, len(texts), batch_size):
            batch = texts[i: i + batch_size]
            batch = [t[:8000] if len(t) > 8000 else t for t in batch]

            payload = {
                "model": self.model,
                "input": batch,
                "input_type": input_type,
                "encoding_format": "float",
            }

            try:
                response = self.session.post(url, json=payload, timeout=120)
                response.raise_for_status()
                data = response.json()
                sorted_data = sorted(data["data"], key=lambda x: x["index"])
                all_embeddings.extend([item["embedding"] for item in sorted_data])
            except requests.exceptions.HTTPError as e:
                logger.error("NVIDIA Embed API: %s — %s", e.response.status_code, e.response.text[:500])
                raise RuntimeError(f"NVIDIA Embed API failed: {e.response.status_code}") from e
            except Exception as e:
                logger.error("NVIDIA Embed failed: %s", str(e))
                raise

        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        return self.embed([text], input_type="query")[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.embed(texts, input_type="passage")


class NvidiaReranker:
    """
    NVIDIA NIM reranking client.

    NVIDIA rerank API uses model-specific URLs:
      https://ai.api.nvidia.com/v1/retrieval/{model_name}/reranking

    NOT the generic /v1/ranking endpoint.
    """

    # Map model names to their correct API endpoint paths
    RERANK_ENDPOINTS = {
        "nvidia/llama-nemotron-rerank-1b-v2": "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-1b-v2/reranking",
        "nvidia/llama-3.2-nv-rerankqa-1b-v2": "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-3.2-nv-rerankqa-1b-v2/reranking",
        "nvidia/llama-3.2-nemoretriever-500m-rerank-v2": "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-3.2-nemoretriever-500m-rerank-v2/reranking",
        "nvidia/rerank-qa-mistral-4b": "https://ai.api.nvidia.com/v1/retrieval/nvidia/rerank-qa-mistral-4b/reranking",
        "nvidia/nv-rerankqa-mistral-4b-v3": "https://ai.api.nvidia.com/v1/retrieval/nvidia/nv-rerankqa-mistral-4b-v3/reranking",
    }

    def __init__(self):
        self.api_key = settings.NVIDIA_API_KEY
        self.model = settings.NVIDIA_RERANK_MODEL
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

        # Resolve the correct endpoint URL
        if self.model in self.RERANK_ENDPOINTS:
            self.url = self.RERANK_ENDPOINTS[self.model]
        else:
            # Build URL from model name
            self.url = f"https://ai.api.nvidia.com/v1/retrieval/{self.model}/reranking"

        logger.info("NvidiaReranker initialized: %s → %s", self.model, self.url)

    def rerank(
        self,
        query: str,
        passages: List[dict],
        top_k: int = 5,
    ) -> List[dict]:
        """
        Rerank passages by relevance to query.
        """
        if not passages or not query:
            return passages[:top_k]

        # Build the request payload
        # NVIDIA rerank API expects: query.text + passages[].text
        documents = []
        for p in passages:
            text = p.get("text", "")
            if text:
                documents.append(text[:4000])

        if not documents:
            return passages[:top_k]

        payload = {
            "model": self.model,
            "query": {"text": query},
            "passages": [{"text": doc} for doc in documents],
        }

        try:
            response = self.session.post(self.url, json=payload, timeout=120)

            # If model-specific URL fails, try alternative endpoint formats
            if response.status_code == 404:
                logger.warning("Rerank endpoint 404, trying alternative URL format...")
                alt_url = f"{settings.NVIDIA_BASE_URL.rstrip('/')}/ranking"
                payload_alt = {
                    "model": self.model,
                    "query": {"text": query},
                    "passages": [{"text": doc} for doc in documents],
                    "top_n": min(top_k, len(documents)),
                }
                response = self.session.post(alt_url, json=payload_alt, timeout=120)

            if response.status_code == 404:
                logger.warning("Rerank endpoint 404 on both URLs, trying OpenAI-compatible format...")
                # Some NVIDIA models use a different payload format
                alt_url2 = f"https://ai.api.nvidia.com/v1/retrieval/{self.model}/reranking"
                payload_v2 = {
                    "model": self.model,
                    "query": {"text": query},
                    "passages": [{"text": doc} for doc in documents],
                }
                response = self.session.post(alt_url2, json=payload_v2, timeout=120)

            response.raise_for_status()
            data = response.json()

            # Parse response — handle different response formats
            rankings = data.get("rankings", [])

            reranked = []
            for rank in rankings:
                idx = rank.get("index", 0)
                if idx < len(passages):
                    passage = passages[idx].copy()
                    passage["rerank_score"] = rank.get("logit", rank.get("score", 0))
                    reranked.append(passage)

            # Sort by score descending and take top_k
            reranked.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
            reranked = reranked[:top_k]

            if reranked:
                logger.info(
                    "Reranked %d → %d (scores: %.3f to %.3f)",
                    len(passages), len(reranked),
                    reranked[0].get("rerank_score", 0),
                    reranked[-1].get("rerank_score", 0),
                )
            return reranked

        except requests.exceptions.HTTPError as e:
            logger.warning(
                "NVIDIA Rerank API failed (%s): %s — falling back to embedding-only results",
                e.response.status_code,
                e.response.text[:300],
            )
            return passages[:top_k]
        except Exception as e:
            logger.warning("NVIDIA Rerank failed: %s — falling back to embedding-only results", str(e))
            return passages[:top_k]