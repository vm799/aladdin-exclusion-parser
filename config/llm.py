"""
OpenAI LLM Configuration
GPT-4 Turbo with Function Calling for Agent Orchestration
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class LLMConfig:
    """
    OpenAI LLM configuration wrapper

    Provides:
    - GPT-4 Turbo as primary model
    - Function calling for agent coordination
    - Cost optimization via caching
    - Error handling and timeouts
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4-turbo",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        timeout: int = 30,
        enable_async: bool = True,
    ):
        """
        Initialize LLM configuration

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model name (gpt-4-turbo, gpt-4, gpt-3.5-turbo)
            temperature: Creativity level 0.0-1.0 (lower = deterministic)
            max_tokens: Max response tokens
            timeout: API timeout in seconds
            enable_async: Enable async client
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

        # Initialize clients
        self.client = OpenAI(api_key=self.api_key, timeout=timeout)
        self.async_client = AsyncOpenAI(api_key=self.api_key, timeout=timeout) if enable_async else None

        logger.info(
            f"Initialized LLMConfig: model={model}, temp={temperature}, "
            f"max_tokens={max_tokens}, async_enabled={enable_async}"
        )

    def create_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Any:
        """
        Create completion with OpenAI API

        Args:
            messages: Chat messages
            tools: Optional tools/functions for function calling
            model: Optional model override
            temperature: Optional temperature override
            max_tokens: Optional token limit override

        Returns:
            OpenAI response object
        """
        model = model or self.model
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens or self.max_tokens

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools if tools else None,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise

    async def create_completion_async(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Any:
        """
        Async version of create_completion

        Args:
            messages: Chat messages
            tools: Optional tools/functions
            model: Optional model override
            temperature: Optional temperature override
            max_tokens: Optional token limit override

        Returns:
            OpenAI response object
        """
        if not self.async_client:
            raise RuntimeError("Async client not enabled")

        model = model or self.model
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens or self.max_tokens

        try:
            response = await self.async_client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools if tools else None,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response
        except Exception as e:
            logger.error(f"OpenAI Async API error: {str(e)}")
            raise

    def extract_tool_calls(self, response: Any) -> List[Dict[str, Any]]:
        """
        Extract function calls from response

        Args:
            response: OpenAI response object

        Returns:
            List of tool calls with id, function name, arguments
        """
        tool_calls = []
        if hasattr(response.choices[0].message, "tool_calls"):
            for tool_call in response.choices[0].message.tool_calls:
                tool_calls.append(
                    {
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": tool_call.function.name,
                        "arguments": json.loads(tool_call.function.arguments),
                    }
                )
        return tool_calls

    def extract_text_response(self, response: Any) -> str:
        """
        Extract text from response

        Args:
            response: OpenAI response object

        Returns:
            Response text
        """
        return response.choices[0].message.content or ""

    @staticmethod
    def estimate_tokens(text: str, model: str = "gpt-4-turbo") -> int:
        """
        Estimate token count (rough approximation)

        Rule of thumb: 1 token ≈ 4 characters

        Args:
            text: Text to estimate
            model: Model name (for future refinement)

        Returns:
            Estimated token count
        """
        return len(text) // 4


# Create default instance
_default_config = None


def get_default_llm_config() -> LLMConfig:
    """Get or create default LLM configuration"""
    global _default_config
    if _default_config is None:
        _default_config = LLMConfig()
    return _default_config


def set_default_llm_config(config: LLMConfig):
    """Set default LLM configuration"""
    global _default_config
    _default_config = config
