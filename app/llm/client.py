"""LLM client abstraction supporting Google Gemini free tier, OpenAI, and Mock fallback.

Provides unified interface for prompt completion and structured JSON reasoning.
Features automatic .env discovery, model fallbacks (gemini-2.0-flash -> gemini-1.5-flash),
and error resilience for free tier quotas.
"""

import logging
import os
from typing import Optional

import httpx

from app.llm.base import BaseLLMClient, load_env_file
from app.llm.mock_client import MockLLMClient

logger = logging.getLogger(__name__)


class GeminiLLMClient(BaseLLMClient):
    """Google Gemini LLM client supporting latest free models with graceful fallbacks."""

    PRIMARY_MODEL = "gemini-3.6-flash"
    BACKUP_MODEL = "gemini-3.5-flash"
    
    def __init__(self, api_key: str, model_name: Optional[str] = None):
        """Initialize Gemini client with API key and default free models."""
        self.api_key = api_key
        self.model_name = model_name or self.PRIMARY_MODEL
        self.is_service_available: bool = True

    def _call_gemini_api(self, model: str, system_prompt: str, user_prompt: str, temperature: float) -> str:
        """Make HTTP POST to Google Gemini REST endpoint."""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            f"?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n\nTask:\n{user_prompt}"}]}],
            "generationConfig": {"temperature": temperature},
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
            if response.status_code in [401 , 403]:
                self.is_service_available = False
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    def generate_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> str:
        """Generate completion trying primary model then backup with offline fallback."""
        if not self.is_service_available:
            return MockLLMClient().generate_completion(system_prompt, user_prompt, temperature)

        try:
            return self._call_gemini_api(self.model_name, system_prompt, user_prompt, temperature)
        except Exception as primary_err:
            if self.is_service_available and self.model_name != self.BACKUP_MODEL:
                try:
                    logger.info(f"Retrying with backup free model '{self.BACKUP_MODEL}'...")
                    return self._call_gemini_api(self.BACKUP_MODEL, system_prompt, user_prompt, temperature)
                except Exception as backup_err:
                    pass
            logger.info("Falling back to deterministic agent reasoning to guarantee uninterrupted execution.")
            mock_client = MockLLMClient()
            return mock_client.generate_completion(system_prompt, user_prompt, temperature)


class OpenAILLMClient(BaseLLMClient):
    """OpenAI API client using standard chat completions."""

    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini"):
        """Initialize OpenAI client."""
        self.api_key = api_key
        self.model_name = model_name
        self.endpoint = "https://api.openai.com/v1/chat/completions"

    def generate_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> str:
        """Call OpenAI chat completions endpoint."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.post(self.endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]


def get_llm_client(force_provider: Optional[str] = None) -> BaseLLMClient:
    """Factory function returning configured LLM client with automatic fallback."""
    load_env_file()

    provider = force_provider or os.environ.get("LLM_PROVIDER", "").lower()

    gemini_key = os.environ.get("GEMINI_API_KEY")
    if (provider == "gemini" or not provider) and gemini_key:
        return GeminiLLMClient(api_key=gemini_key)

    openai_key = os.environ.get("OPENAI_API_KEY")
    if (provider == "openai" or not provider) and openai_key:
        return OpenAILLMClient(api_key=openai_key)

    return MockLLMClient()
