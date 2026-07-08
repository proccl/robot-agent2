import json
import re
from pathlib import Path


def _readme_text():
    root = Path(__file__).resolve().parent.parent
    return (root / "README.md").read_text(encoding="utf-8")


def _extract_quick_start_blocks(readme_text):
    """Extract the PowerShell and Bash code blocks under ## Quick Start."""
    match = re.search(r"## Quick Start\n+(.*?)(?=\n## |\Z)", readme_text, re.DOTALL)
    if not match:
        return None, None

    section = match.group(1)
    blocks = re.findall(r"### (.*?)\n+```(\w+)\n(.*?)```", section, re.DOTALL)

    ps_block = None
    bash_block = None
    for title, lang, code in blocks:
        if "PowerShell" in title or lang.lower() == "powershell":
            ps_block = code
        elif "Bash" in title or lang.lower() == "bash":
            bash_block = code
    return ps_block, bash_block


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
    assert (root / "skills" / "robotagent2-ops" / "references" / "hardware-reference.md").exists()


def test_quick_start_has_windows_and_bash_sections():
    ps, bash = _extract_quick_start_blocks(_readme_text())
    assert ps is not None, "Quick Start is missing Windows PowerShell section"
    assert bash is not None, "Quick Start is missing Linux/macOS Bash section"


def test_quick_start_powershell_no_bash_syntax():
    ps, _ = _extract_quick_start_blocks(_readme_text())
    assert "<<" not in ps, "PowerShell Quick Start contains Bash here-document syntax '<<'"
    assert "$(date" not in ps, "PowerShell Quick Start contains Bash command substitution '$(date'"


def test_quick_start_bash_has_heredoc():
    _, bash = _extract_quick_start_blocks(_readme_text())
    assert "<< 'PYEOF'" in bash or "<< PYEOF" in bash, "Bash Quick Start is missing expected here-document syntax"


def test_readme_quick_start_no_absolute_project_path():
    ps, bash = _extract_quick_start_blocks(_readme_text())
    absolute_path = "D:\\software package\\NexArm模仿学习机械臂\\robot-agent2"
    assert absolute_path not in ps, "PowerShell Quick Start contains absolute project path"
    assert absolute_path.replace("\\", "/") not in bash, "Bash Quick Start contains absolute project path"
