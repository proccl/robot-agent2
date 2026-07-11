from pathlib import Path

import pytest

from src.skill_context import SkillContext


@pytest.fixture
def sample_skill(tmp_path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        "# SKILL\n\nThis project controls a NexArm robot arm.\n\n"
        "## Movement\n\nUse `relative_move(dx, dy, dz)` to move the end-effector.\n\n"
        "## Claw\n\nUse `set_claw(angle)` to open or close the gripper.\n",
        encoding="utf-8",
    )
    return str(skill_md)


@pytest.fixture
def sample_json(tmp_path):
    json_file = tmp_path / "commands.json"
    json_file.write_text(
        '{"home": "Go to home position", "forward": "Move forward"}',
        encoding="utf-8",
    )
    return str(json_file)


def test_loads_markdown_chunks(sample_skill):
    ctx = SkillContext([sample_skill])
    assert len(ctx.chunks) >= 2
    titles = {chunk["title"] for chunk in ctx.chunks}
    assert "SKILL" in titles
    assert "Movement" in titles
    assert "Claw" in titles


def test_retrieve_movement(sample_skill):
    ctx = SkillContext([sample_skill])
    results = ctx.retrieve("How do I move the arm forward?")
    assert len(results) >= 1
    assert any("relative_move" in r["content"] for r in results)


def test_retrieve_claw(sample_skill):
    ctx = SkillContext([sample_skill])
    results = ctx.retrieve("open the gripper")
    assert any("claw" in r["content"].lower() or "gripper" in r["content"].lower() for r in results)


def test_top_k_limits_results(sample_skill):
    ctx = SkillContext([sample_skill])
    results = ctx.retrieve("arm claw move", top_k=2)
    assert len(results) <= 2


def test_format_chunks(sample_skill):
    ctx = SkillContext([sample_skill])
    chunks = ctx.retrieve("move")
    formatted = ctx.format_chunks(chunks)
    assert "relative_move" in formatted
    assert "Source:" in formatted


def test_loads_json_reference(sample_skill, sample_json):
    ctx = SkillContext([sample_skill, sample_json])
    json_chunks = [c for c in ctx.chunks if c["source"].endswith(".json")]
    assert len(json_chunks) == 1
    assert "home" in json_chunks[0]["content"]


def test_retrieve_from_config_paths():
    root = Path(__file__).resolve().parent.parent
    cfg = __import__("yaml").safe_load(
        (root / "config" / "config.yaml").read_text(encoding="utf-8")
    )
    paths = cfg["llm"]["skill_context"]
    ctx = SkillContext(paths)
    assert len(ctx.chunks) > 0
    results = ctx.retrieve("move the arm forward")
    assert len(results) >= 1
