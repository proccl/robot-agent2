import pytest

from src.llm_client import LLMError
from src.natural_language import NaturalLanguagePlanner
from src.skill_context import SkillContext


class MockLLMClient:
    """A fake LLM client that returns a fixed response."""

    def __init__(self, response="interface.home()\nprint('done')"):
        self.response = response
        self.last_messages = None

    def chat(self, messages):
        self.last_messages = messages
        return self.response


@pytest.fixture
def planner(tmp_path):
    client = MockLLMClient()
    skill = SkillContext([])
    return NaturalLanguagePlanner(client, skill, tmp_path / "incoming")


def test_generate_script_uses_client_and_returns_content(planner):
    script = planner.generate_script("go home")
    assert "interface.home()" in script
    assert planner.client.last_messages is not None
    assert any(m["role"] == "user" and "go home" in m["content"] for m in planner.client.last_messages)


def test_clean_script_strips_markdown_fences(planner):
    raw = "```python\ninterface.home()\n```"
    assert planner._clean_script(raw) == "interface.home()"


def test_save_script_creates_incoming_file(planner):
    path = planner.save_script("go home", "interface.home()")
    assert path.exists()
    assert path.parent.name == "incoming"
    assert "cmd_" in path.name
    assert "go_home" in path.name
    assert path.read_text(encoding="utf-8") == "interface.home()"


def test_plan_and_save_combines_steps(planner):
    path = planner.plan_and_save("return to home")
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "interface.home()" in content


def test_from_config_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("SJTU_API_KEY", raising=False)
    with pytest.raises(LLMError):
        NaturalLanguagePlanner.from_config()
