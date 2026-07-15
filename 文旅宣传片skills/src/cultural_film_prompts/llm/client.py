"""LLM 适配层 —— OpenAI 兼容接口。

支持两种结构化输出：
1. function_calling（推荐）：通过 tool/function schema 强制 JSON 输出
2. json_mode：通过 response_format={"type": "json_object"} 强制 JSON

适配 DeepSeek / 通义千问 / OpenAI 等兼容接口。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMResponse:
    """LLM 响应封装"""

    raw_text: str
    parsed: BaseModel | None
    usage: dict[str, int]  # {"prompt_tokens": N, "completion_tokens": N}
    model: str

    def parsed_or_raise(self, model_cls: Type[T]) -> T:
        if isinstance(self.parsed, model_cls):
            return self.parsed
        raise ValueError(
            f"响应类型不匹配，期望 {model_cls.__name__}，"
            f"实际 {type(self.parsed).__name__ if self.parsed else 'None'}"
        )


class LLMClient:
    """OpenAI 兼容 LLM 客户端"""

    def __init__(self, base_url: str, api_key: str, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._http = httpx.Client(timeout=timeout)

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tools: list[dict] | None = None,
        tool_choice: dict | str | None = None,
        response_format: dict | None = None,
    ) -> dict:
        """调用 /chat/completions 接口"""

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"

        if response_format:
            payload["response_format"] = response_format

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.debug(f"LLM 请求: {url} model={model}")
        resp = self._http.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


# —— 结构化输出封装 ——


def _build_tool_schema(model_cls: Type[BaseModel]) -> dict:
    """把 Pydantic 模型转成 OpenAI function calling 的 tool schema"""
    schema = model_cls.model_json_schema()
    # 清理 $defs 引用，OpenAI tool 不支持嵌套 $ref 的某些实现
    return {
        "type": "function",
        "function": {
            "name": model_cls.__name__,
            "description": model_cls.__doc__ or f"Output as {model_cls.__name__}",
            "parameters": schema,
        },
    }


def structured_call(
    client: LLMClient,
    model: str,
    system_prompt: str,
    user_prompt: str,
    output_model: Type[T],
    temperature: float = 0.7,
    max_tokens: int = 2000,
    structured_mode: str = "function_calling",
) -> LLMResponse:
    """
    结构化输出调用。

    Args:
        client: LLM 客户端
        model: 模型名
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        output_model: 期望的输出 Pydantic 模型
        temperature: 温度
        max_tokens: 最大输出 token
        structured_mode: function_calling | json_mode
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    parsed: BaseModel | None = None
    raw_text: str = ""
    usage: dict[str, int] = {}

    if structured_mode == "function_calling":
        tool_schema = _build_tool_schema(output_model)
        result = client.chat(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=[tool_schema],
            tool_choice={"type": "function", "function": {"name": output_model.__name__}},
        )

        msg = result["choices"][0]["message"]
        usage = result.get("usage", {}).get("total_tokens", 0)

        if "tool_calls" in msg and msg["tool_calls"]:
            args_str = msg["tool_calls"][0]["function"]["arguments"]
            raw_text = args_str
            try:
                args_dict = json.loads(args_str)
                parsed = output_model.model_validate(args_dict)
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error(f"function_calling 解析失败: {e}")
                parsed = None
        else:
            raw_text = msg.get("content", "")
            logger.warning("LLM 未返回 tool_calls，尝试解析 content")

    elif structured_mode == "json_mode":
        result = client.chat(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

        msg = result["choices"][0]["message"]
        raw_text = msg.get("content", "")
        usage = result.get("usage", {}).get("total_tokens", 0)

        try:
            data = json.loads(raw_text)
            parsed = output_model.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"json_mode 解析失败: {e}")
            parsed = None

    else:
        raise ValueError(f"不支持的 structured_mode: {structured_mode}")

    return LLMResponse(
        raw_text=raw_text,
        parsed=parsed,
        usage={"total_tokens": usage},
        model=model,
    )
