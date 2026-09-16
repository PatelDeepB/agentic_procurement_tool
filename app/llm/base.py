"""Base LLM interface and environment discovery utilities."""

from abc import ABC, abstractmethod
import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)


def load_env_file(filepath: str = ".env") -> None:
    """Load environment variables from a local .env file if present."""
    if not os.path.exists(filepath):
        return
    try:
        with open(filepath, "r", encoding="utf-8") as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                clean_key = key.strip()
                clean_val = val.strip().strip("'\"")
                if clean_key and clean_key not in os.environ:
                    os.environ[clean_key] = clean_val
    except Exception as err:
        logger.warning(f"Could not parse local .env file: {err}")


class BaseLLMClient(ABC):
    """Abstract interface for multi-agent LLM reasoning clients."""

    is_service_available: bool = True

    @abstractmethod
    def generate_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> str:
        """Generate raw text response from the language model."""
        pass

    @staticmethod
    def extract_json(raw_text: str) -> Dict[str, Any]:
        """Extract and parse structured JSON dictionary from raw model text."""
        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return json.loads(cleaned.strip())

    def generate_structured_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        """Generate and parse structured JSON response from the language model."""
        raw_text = self.generate_completion(system_prompt, user_prompt, temperature=temperature)
        return self.extract_json(raw_text)

