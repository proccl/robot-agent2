import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

import pytest
import yaml

from src.llm_client import LLMClient, LLMError


class MockLLMHandler(BaseHTTPRequestHandler):
    """A tiny OpenAI-compatible mock server for unit tests."""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        stream = body.get("stream", False)

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/event-stream" if stream else "application/json",
        )
        self.end_headers()

        if stream:
            for token in ["Hello", " ", "world"]:
                data = json.dumps({"choices": [{"delta": {"content": token}}]})
                self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
        else:
            response = {
                "choices": [{"message": {"content": "Hello world"}}],
            }
            self.wfile.write(json.dumps(response).encode("utf-8"))

    def log_message(self, format, *args):
        pass


@pytest.fixture
def mock_server():
    server = HTTPServer(("127.0.0.1", 0), MockLLMHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def client(mock_server):
    return LLMClient(
        base_url=mock_server,
        api_key="test-key",
        model="test-model",
        temperature=0.3,
        max_tokens=2048,
    )


def test_chat_returns_content(client):
    messages = [{"role": "user", "content": "hi"}]
    assert client.chat(messages) == "Hello world"


def test_chat_stream_yields_content(client):
    messages = [{"role": "user", "content": "hi"}]
    tokens = list(client.chat_stream(messages))
    assert "".join(tokens) == "Hello world"


def test_request_failure_raises_llm_error():
    client = LLMClient(
        base_url="http://127.0.0.1:1",
        api_key="k",
        model="m",
    )
    with pytest.raises(LLMError):
        client.chat([{"role": "user", "content": "hi"}])


def test_client_from_config(mock_server, monkeypatch):
    root = Path(__file__).resolve().parent.parent
    cfg = yaml.safe_load((root / "config" / "config.yaml").read_text(encoding="utf-8"))
    llm_cfg = cfg["llm"]
    monkeypatch.setenv("SJTU_API_KEY", "test-key")
    client = LLMClient(
        base_url=mock_server,
        api_key=os.environ["SJTU_API_KEY"],
        model=llm_cfg["model"],
        temperature=llm_cfg.get("default_temperature", 0.3),
        max_tokens=llm_cfg.get("default_max_tokens", 2048),
    )
    assert client.chat([{"role": "user", "content": "hi"}]) == "Hello world"


def test_sanitize_text_removes_surrogates():
    text = "hello \udcab world"
    cleaned = LLMClient._sanitize_text(text)
    assert "\udcab" not in cleaned
