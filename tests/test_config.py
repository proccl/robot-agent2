import os
from pathlib import Path
import yaml


def test_config_exists_and_loads():
    root = Path(__file__).resolve().parent.parent
    config_path = root / "config" / "config.yaml"
    assert config_path.exists(), "config.yaml not found"
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert cfg["port"] == "COM5"
    assert cfg["baudrate"] == 1000000
    assert "workspace_limits" in cfg
    assert "nexarm_sdk_path" in cfg


def test_directory_structure():
    root = Path(__file__).resolve().parent.parent
    required_dirs = [
        "src",
        "config",
        "docs",
        "tests",
        "skills/robotagent2-ops/references",
        "incoming",
        "incoming/failed",
        "incoming_history",
        "logs",
    ]
    for d in required_dirs:
        assert (root / d).is_dir(), f"missing directory: {d}"


def test_plan_backup_exists():
    root = Path(__file__).resolve().parent.parent
    assert (root / "docs" / "plan.md").exists(), "plan backup not found"


def test_llm_config_loads():
    root = Path(__file__).resolve().parent.parent
    config_path = root / "config" / "config.yaml"
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert "llm" in cfg, "llm section not found in config"
    llm = cfg["llm"]
    assert llm.get("provider") == "sjtu"
    assert llm.get("base_url") == "https://models.sjtu.edu.cn/api/v1"
    assert llm.get("model") == "qwen3.6-27b"
    assert llm.get("api_key_env") == "SJTU_API_KEY"
    assert "skill_context" in llm
    assert isinstance(llm["skill_context"], list)
    assert "skills/robotagent2-ops/SKILL.md" in llm["skill_context"]
