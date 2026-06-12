import base64
import json
import re
from typing import Any

from openai import AsyncOpenAI

from .config import settings
from json_repair import repair_json


def image_to_base64(image_path: str) -> str:
    """Convert image file to base64 encoded string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


class VLLMClient:
    """Tiny OpenAI-compatible client for vLLM /v1/chat/completions."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.vllm_base_url).rstrip("/")
        self.api_key = api_key or settings.vllm_api_key
        self.model = model or settings.vllm_model
        
        # 初始化 OpenAI 客户端
        # 使用 httpx 禁用代理，避免与系统代理冲突
        import httpx
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            http_client=httpx.AsyncClient(
                trust_env=False,
                timeout=settings.vllm_timeout_seconds,
            ),
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 50048,
        json_mode: bool = False,
        image_paths: list[str] | None = None,
    ) -> str:
        # 构建请求参数
        params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "extra_body": {
                "chat_template_kwargs": {"enable_thinking": False}  # 关闭思考模式
            },
        }

        # vLLM's OpenAI-compatible server supports OpenAI-style response_format for many
        # chat models. If your served model/template does not support this, set json_mode=False
        # and json_chat() will still try to extract the first JSON object from the response.
        if json_mode:
            params["response_format"] = {"type": "json_object"}

        # 如果提供了图片路径，构建包含图片的消息
        if image_paths and len(image_paths) > 0:
            content: list[dict[str, Any]] = []
            
            # 添加图片
            for img_path in image_paths:
                image_base64 = image_to_base64(img_path)
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                })
            
            # 如果原消息中有 user 角色，将文本内容添加到 content
            if messages:
                last_msg = messages[-1]
                if last_msg.get("role") == "user" and isinstance(last_msg.get("content"), str):
                    content.append({
                        "type": "text",
                        "text": last_msg["content"]
                    })
            
            # 替换最后一条消息为包含图片的内容
            messages = messages[:-1] + [{
                "role": "user",
                "content": content
            }]
            params["messages"] = messages

        # 发送请求
        completion = await self.client.chat.completions.create(**params)
        return completion.choices[0].message.content or ""

    async def json_chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 50048,
    ) -> dict[str, Any]:
        content = await self.chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        content = repair_json(content, return_objects=True)
        # Ensure we always return a dict, not None
        return content if isinstance(content, dict) else {}


llm = VLLMClient()
