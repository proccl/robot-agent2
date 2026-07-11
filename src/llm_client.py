"""OpenAI-compatible LLM client for SJTU and other providers."""
import json
import urllib.request
from typing import Iterator, List, Dict, Optional


class LLMError(Exception):
    """Raised when the LLM API returns an error or the request fails."""


class LLMClient:
    """Minimal OpenAI-compatible chat client using only the standard library."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat(self, messages: List[Dict[str, str]]) -> str:
        """Send a non-streaming chat request and return the assistant's content."""
        response = self._request(messages, stream=False)
        return self._extract_content(response)

    def chat_stream(self, messages: List[Dict[str, str]]) -> Iterator[str]:
        """Send a streaming chat request and yield assistant content tokens."""
        response = self._request(messages, stream=True)
        yield from self._stream_content(response)

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Remove surrogate characters that break JSON encoding on Windows."""
        return text.encode("utf-8", "surrogatepass").decode("utf-8", "replace")

    def _request(self, messages: List[Dict[str, str]], stream: bool = False):
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": m["role"], "content": self._sanitize_text(m["content"])}
                for m in messages
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": stream,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            return urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError as e:
            raise LLMError(
                f"LLM API error {e.code}: {e.read().decode('utf-8', errors='replace')}"
            ) from e
        except Exception as e:
            raise LLMError(f"LLM request failed: {e}") from e

    def _extract_content(self, response) -> str:
        data = json.loads(response.read().decode("utf-8"))
        if "choices" not in data or not data["choices"]:
            raise LLMError("Invalid response from LLM API: no choices")
        return data["choices"][0]["message"]["content"]

    def _stream_content(self, response) -> Iterator[str]:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                data = json.loads(data_str)
                delta = data.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content
            except (json.JSONDecodeError, KeyError, IndexError):
                continue
