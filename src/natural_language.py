"""Convert natural-language instructions into executable NexArm Python scripts."""
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml

from src.llm_client import LLMClient, LLMError
from src.skill_context import SkillContext


class NaturalLanguagePlanner:
    """Uses skill context + LLM to generate robot command scripts."""

    def __init__(
        self,
        client: LLMClient,
        skill_context: SkillContext,
        incoming_dir: Path,
    ):
        self.client = client
        self.skill_context = skill_context
        self.incoming_dir = Path(incoming_dir)
        self.incoming_dir.mkdir(parents=True, exist_ok=True)
        self.system_prompt = self._build_system_prompt()

    @classmethod
    def from_config(
        cls,
        config_path: str = "config/config.yaml",
        incoming_dir: Optional[Path] = None,
    ):
        """Build a planner from the project config file."""
        root = Path(config_path).resolve().parent.parent
        cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
        llm_cfg = cfg["llm"]

        skill_context = SkillContext(
            [str(root / p) for p in llm_cfg.get("skill_context", [])]
        )

        api_key_env = llm_cfg.get("api_key_env", "SJTU_API_KEY")
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise LLMError(
                f"API key environment variable {api_key_env} is not set."
            )

        client = LLMClient(
            base_url=llm_cfg["base_url"],
            api_key=api_key,
            model=llm_cfg["model"],
            temperature=llm_cfg.get("default_temperature", 0.3),
            max_tokens=llm_cfg.get("default_max_tokens", 2048),
        )
        return cls(client, skill_context, incoming_dir or root / "incoming")

    def _build_system_prompt(self) -> str:
        """Build a system prompt that includes general skill context."""
        chunks = self.skill_context.retrieve("general operation")
        context = self.skill_context.format_chunks(chunks)
        return (
            "You are a Python coding assistant for the NexArm 6-DOF robot arm.\n"
            "Convert the user's natural-language instruction into a short, safe Python script.\n\n"
            "Rules:\n"
            "1. Use only the provided `interface` object (NexArmInterface).\n"
            "2. Do NOT create classes, functions, or helper variables unless necessary.\n"
            "3. Return ONLY the Python script body. No markdown fences, no explanations.\n"
            "4. Prefer concrete motions: home(), relative_move(dx, dy, dz), move_to(x, y, z, ...), set_claw(angle).\n"
            "5. The script may read `state` (a dict) but should not modify it.\n"
            "6. Always end with a comment or print so the user sees completion.\n\n"
            "Available NexArmInterface methods:\n"
            "- interface.home(duration=None, wait=True)\n"
            "- interface.move_to(x, y, z, duration=None, pitch=0, roll=0, claw=0, wait=True)\n"
            "- interface.relative_move(dx, dy, dz, duration=None, dpitch=0, droll=0, dclaw=0, wait=True)\n"
            "- interface.joint_move(servo_id, pos, duration=None, wait=True)\n"
            "- interface.line(target=(x,y,z), duration=None, steps=10, wait=True)\n"
            "- interface.circle(center=(x,y,z), radius, duration=None, steps=20, wait=True)\n"
            "- interface.warmup()\n"
            "- interface.get_status() -> dict with keys x, y, z, pitch, roll, claw, servos\n\n"
            "Project reference context:\n"
            f"{context}\n"
        )

    def generate_script(self, instruction: str) -> str:
        """Ask the LLM to generate a script for the given instruction."""
        chunks = self.skill_context.retrieve(instruction)
        prompt = self.system_prompt
        if chunks:
            prompt += (
                "\n\nRelevant reference sections for this instruction:\n"
                + self.skill_context.format_chunks(chunks)
            )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": instruction},
        ]
        script = self.client.chat(messages)
        return self._clean_script(script)

    @staticmethod
    def _clean_script(script: str) -> str:
        """Strip markdown fences and leading/trailing whitespace."""
        script = script.strip()
        if script.startswith("```python"):
            script = script[len("```python"):]
        elif script.startswith("```"):
            script = script[len("```"):]
        if script.endswith("```"):
            script = script[:-len("```")]
        return script.strip()

    def save_script(self, instruction: str, script: str) -> Path:
        """Save the generated script to the incoming directory.

        The filename uses a timestamp plus an ASCII-safe suffix to avoid
        encoding issues on Windows with non-ASCII descriptions.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Keep only ASCII word characters to avoid Windows filename issues.
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", instruction).strip("_")[:30]
        suffix = safe if safe else "llm"
        filename = f"cmd_{timestamp}_{suffix}.py"
        path = self.incoming_dir / filename
        path.write_text(script, encoding="utf-8")
        return path

    def plan_and_save(self, instruction: str) -> Path:
        """Generate and save a script in one step."""
        script = self.generate_script(instruction)
        return self.save_script(instruction, script)
