"""LLM client abstraction layer (§3A).
Only this file may import a provider SDK.
"""

import os
import json
import asyncio
from dataclasses import dataclass, field
from typing import Optional
from abc import ABC, abstractmethod
from dotenv import load_dotenv
load_dotenv()


@dataclass
class ToolCall:
    name: str
    args: dict
    id: str = ""


@dataclass
class LLMResult:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict = field(default_factory=lambda: {"in": 0, "cached_in": 0, "out": 0})


class BaseLLMClient(ABC):
    """Interface all providers must implement."""

    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        json_schema: dict | None = None,
        timeout: float = 6.0,
    ) -> LLMResult:
        ...


class OpenAIClient(BaseLLMClient):
    """OpenAI Chat Completions with tool calling (default provider)."""

    def __init__(self, model: str = None):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("Install openai: pip install openai")

        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        json_schema: dict | None = None,
        timeout: float = 6.0,
    ) -> LLMResult:
        # Build messages — system first for prefix caching (§3A)
        api_messages = [{"role": "system", "content": system}]
        api_messages.extend(messages)

        kwargs = {
            "model": self.model,
            "messages": api_messages,
            "temperature": 0.3,
            "max_tokens": 500,
            "timeout": timeout,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if json_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": json_schema,
                    "strict": True,
                }
            }

        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(**kwargs),
                timeout=timeout + 2,
            )
        except asyncio.TimeoutError:
            return LLMResult(text="[TIMEOUT] LLM did not respond in time.")
        except Exception as e:
            return LLMResult(text=f"[ERROR] LLM call failed: {str(e)}")

        message = response.choices[0].message
        result = LLMResult()

        # Extract text
        if message.content:
            result.text = message.content

        # Extract tool calls
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {"_raw": tc.function.arguments}
                result.tool_calls.append(ToolCall(name=tc.function.name, args=args, id=tc.id))

        # Usage
        if response.usage:
            result.usage = {
                "in": response.usage.prompt_tokens,
                "cached_in": getattr(response.usage, "prompt_tokens_cached", 0) or 0,
                "out": response.usage.completion_tokens,
            }

        return result


class MockLLMClient(BaseLLMClient):
    """Fallback client for testing without an API key."""

    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        json_schema: dict | None = None,
        timeout: float = 6.0,
    ) -> LLMResult:
        last_msg = messages[-1]["content"] if messages else ""
        return LLMResult(
            text=f"[MOCK LLM] Received: {last_msg[:100]}... I would normally process this with tools.",
            tool_calls=[],
            usage={"in": 100, "cached_in": 50, "out": 30},
        )


def get_llm_client() -> BaseLLMClient:
    """Factory: select provider from env var (§3A)."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    api_key = os.getenv("OPENAI_API_KEY", "")

    if provider == "openai" and api_key and not api_key.startswith("sk-your"):
        return OpenAIClient()
    elif provider == "mock" or not api_key or api_key.startswith("sk-your"):
        print("[INFO] Using MockLLMClient — set OPENAI_API_KEY for real LLM")
        return MockLLMClient()
    else:
        print(f"[WARN] Unknown LLM_PROVIDER={provider}, falling back to mock")
        return MockLLMClient()
