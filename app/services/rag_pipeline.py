"""
RAG pipeline — with max_tokens passthrough for long responses.
"""

import logging
from typing import List, Dict, Any

from app.config import settings
from app.services.vector_store import VectorStoreService

logger = logging.getLogger(__name__)


def _get_llm_response(
    prompt: str,
    system_prompt: str = "",
    temperature: float | None = None,
    max_tokens: int | None = None,
    json_mode: bool = False,
    provider_override: str | None = None,
) -> str:
    provider = (provider_override or settings.LLM_PROVIDER).lower()

    if provider == "nvidia":
        try:
            from app.services.nvidia_embedder import NvidiaLLM
            llm = NvidiaLLM()
            return llm.chat(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
            )
        except Exception as e:
            logger.warning("NVIDIA LLM failed, trying fallback: %s", str(e))
            fallback = settings.FALLBACK_LLM_PROVIDER.lower()
            if fallback and fallback != "nvidia":
                return _get_llm_response(
                    prompt, system_prompt, temperature, max_tokens,
                    json_mode=False, provider_override=fallback,
                )
            raise

    elif provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        kwargs = {
            "model": settings.OPENAI_MODEL,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE,
            "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
        }
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    elif provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        response = model.generate_content(full_prompt)
        return response.text or ""

    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


class RAGPipeline:
    def __init__(self):
        self.vs = VectorStoreService()

    def retrieve_context(
        self,
        course_id: int,
        query: str,
        top_k: int = 8,
        use_reranker: bool | None = None,
    ) -> List[Dict[str, Any]]:
        collection_name = f"course_{course_id}"
        should_rerank = use_reranker if use_reranker is not None else settings.USE_RERANKER

        if should_rerank:
            results = self.vs.search_with_rerank(
                collection_name, query,
                initial_top_k=settings.RETRIEVAL_TOP_K,
                final_top_k=settings.RERANK_TOP_K,
            )
        else:
            results = self.vs.search(collection_name, query, top_k=top_k)

        logger.info("Retrieved %d passages for course %d (reranked=%s)", len(results), course_id, should_rerank)
        return results

    def generate_with_context(
        self,
        context_passages: List[Dict[str, Any]],
        user_prompt: str,
        system_prompt: str = "",
        temperature: float | None = None,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        context_parts = []
        for i, p in enumerate(context_passages):
            text = p.get("text", "")
            if not text:
                continue
            score_info = ""
            if "rerank_score" in p:
                score_info = f" [relevance: {p['rerank_score']:.3f}]"
            context_parts.append(f"[Passage {i + 1}{score_info}]\n{text}")

        context_text = "\n\n---\n\n".join(context_parts)
        full_prompt = (
            f"### CONTEXT (course material — use ONLY this):\n"
            f"{context_text}\n\n"
            f"### INSTRUCTION:\n{user_prompt}"
        )
        return _get_llm_response(
            full_prompt, system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )

    def query(
        self,
        course_id: int,
        user_prompt: str,
        system_prompt: str = "",
        top_k: int = 8,
    ) -> str:
        passages = self.retrieve_context(course_id, user_prompt, top_k)
        if not passages:
            logger.warning("No passages found for course %d", course_id)
            return _get_llm_response(user_prompt, system_prompt)
        return self.generate_with_context(passages, user_prompt, system_prompt)


def call_llm(
    prompt: str,
    system_prompt: str = "",
    temperature: float | None = None,
    json_mode: bool = False,
    max_tokens: int | None = None,
) -> str:
    return _get_llm_response(
        prompt, system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=json_mode,
    )