import json
from pathlib import Path


def test_robot_agent2_cmds_json_is_valid():
    root = Path(__file__).resolve().parent.parent
    json_path = root / "docs" / "robot_agent2_cmds.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert "commands" in data
    assert "home" in data["commands"]


def test_readme_files_exist():
    root = Path(__file__).resolve().parent.parent
    assert (root / "README.md").exists()
    assert (root / "docs" / "README.md").exists()


def test_skill_files_exist():
    root = Path(__file__).resolve().parent.parent
    assert (root / "skills" / "robotagent2-ops" / "SKILL.md").exists()
    assert (root / "skills" / "robotagent2-ops" / "references" / "architecture-reference.md").exists()
    assert (root / "skills" / "robotagent2-ops" / "references" / "script-templates-reference.md").exists()
    assert (root / "skills" / "robotagent2-ops" / "references" / "troubleshooting-reference.md").exists()
