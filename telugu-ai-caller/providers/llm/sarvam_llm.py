"""
Sarvam AI LLM Provider Implementation (Token Factory).
"""

import time
from typing import List, Dict, Any
from loguru import logger

from providers.llm.base import BaseLLMProvider
from services.sarvam_service import sarvam_client
from services.sales_agent import sales_agent
from config import SARVAM_API_KEY, DEFAULT_LLM_MODEL


class SarvamLLMProvider(BaseLLMProvider):
    def __init__(self):
        super().__init__(provider_name="sarvam_llm")
        self.api_key = SARVAM_API_KEY
        self.default_model = DEFAULT_LLM_MODEL

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 5)

    def get_masked_config(self) -> Dict[str, Any]:
        return {
            "api_key": self.mask_secret(self.api_key),
            "model": self.default_model,
            "context_window": 8192
        }

    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.5,
        max_tokens: int = 200
    ) -> str:
        return await sarvam_client.chat_completion(
            messages=messages,
            model=self.default_model,
            temperature=temperature,
            max_tokens=max_tokens
        )

    async def extract_intelligence(
        self,
        conversation_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        return await sales_agent.extract_call_intelligence(conversation_history)

    async def test_connection(self) -> Dict[str, Any]:
        start = time.time()
        if not self.is_configured():
            return {
                "success": False,
                "latency_ms": 0,
                "message": "Sarvam API Key is missing in environment (.env).",
                "details": {"error": "UNCONFIGURED"}
            }

        try:
            test_messages = [
                {"role": "system", "content": "You are a test ping agent. Reply with the single word 'PONG'."},
                {"role": "user", "content": "ping"}
            ]
            reply = await self.complete(test_messages, temperature=0.1, max_tokens=10)
            latency = round((time.time() - start) * 1000, 1)

            return {
                "success": True,
                "latency_ms": latency,
                "message": f"Sarvam LLM verified ({latency}ms). Response: {reply[:30]}",
                "details": {"model": self.default_model}
            }
        except Exception as e:
            latency = round((time.time() - start) * 1000, 1)
            return {
                "success": False,
                "latency_ms": latency,
                "message": f"Sarvam LLM test failed: {str(e)}",
                "details": {"error": str(e)}
            }

