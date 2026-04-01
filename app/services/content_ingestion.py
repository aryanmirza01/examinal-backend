"""
Parse uploaded files (PDF, DOCX, PPTX) and chunk them into passages.
"""

import logging
from typing import List, Dict, Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.utils.file_parser import parse_pdf, parse_docx, parse_pptx

logger = logging.getLogger(__name__)


class ContentIngestionService:
    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def parse_and_chunk(self, file_path: str, file_type: str) -> List[Dict[str, Any]]:
        """
        Return list of {"text": str, "page": int | None}.
        """
        logger.info("Parsing %s (%s)", file_path, file_type)

        if file_type == "pdf":
            pages = parse_pdf(file_path)
        elif file_type == "docx":
            pages = parse_docx(file_path)
        elif file_type == "pptx":
            pages = parse_pptx(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        passages: List[Dict[str, Any]] = []
        for page_data in pages:
            text = page_data["text"].strip()
            if not text:
                continue
            chunks = self.splitter.split_text(text)
            for chunk in chunks:
                if len(chunk.strip()) < 20:
                    continue
                passages.append({
                    "text": chunk.strip(),
                    "page": page_data.get("page"),
                })

        logger.info("Created %d passages from %s", len(passages), file_path)
        return passages