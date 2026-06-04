"""Thin Gemini wrapper for tool-calling chat sessions."""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any

import google.generativeai as genai
from google.generativeai.types import content_types

from tools.schemas import tool_declarations

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall]


class GeminiAgent:
    def __init__(self, api_key: str, system_prompt: str, model: str = DEFAULT_MODEL):
        genai.configure(api_key=api_key)
        tools = [content_types.protos.Tool(function_declarations=tool_declarations())]
        self.model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
            tools=tools,
        )
        self.chat = self.model.start_chat(enable_automatic_function_calling=False)

    def send(self, message: Any, max_retries: int = 3) -> LLMResponse:
        """Send a user message or a list of function-response Parts; return text + tool calls.

        Retries on 429 rate-limit errors using the retry_delay hint from the API.
        """
        for attempt in range(max_retries + 1):
            try:
                response = self.chat.send_message(message)
                break
            except Exception as e:
                msg = str(e)
                if "429" not in msg or attempt == max_retries:
                    raise
                wait_match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", msg)
                wait = int(wait_match.group(1)) + 2 if wait_match else 15
                print(f"  [rate-limited; sleeping {wait}s and retrying ({attempt+1}/{max_retries})]", flush=True)
                time.sleep(wait)
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for cand in response.candidates:
            for part in cand.content.parts:
                if getattr(part, "function_call", None) and part.function_call.name:
                    fc = part.function_call
                    args = {k: v for k, v in (fc.args or {}).items()}
                    tool_calls.append(ToolCall(name=fc.name, args=args))
                elif getattr(part, "text", None):
                    text_parts.append(part.text)
        return LLMResponse(text="\n".join(text_parts).strip(), tool_calls=tool_calls)

    @staticmethod
    def function_response_part(name: str, result: str) -> Any:
        """Build a Part that returns a tool result to the model."""
        return content_types.protos.Part(
            function_response=content_types.protos.FunctionResponse(
                name=name,
                response={"result": result},
            )
        )
