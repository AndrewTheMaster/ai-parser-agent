"""Load PipelineConfig from environment (.env supported via python-dotenv)."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from app.schemas.term import PipelineConfig

load_dotenv()


def load_pipeline_config() -> PipelineConfig:
    return PipelineConfig(
        llm_base_url=os.getenv("LLM_BASE_URL", "http://127.0.0.1:1234/v1"),
        llm_api_key=os.getenv("LLM_API_KEY", "lm-studio"),
        llm_model=os.getenv("LLM_MODEL", "local-model"),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
        top_k_definitions=int(os.getenv("TOP_K_DEFINITIONS", "3")),
        bm25_top_k_chunks=int(os.getenv("BM25_TOP_K_CHUNKS", "40")),
    )
