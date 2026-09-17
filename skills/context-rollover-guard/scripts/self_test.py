"""Offline smoke test of the shipped CLI; no live Codex requests."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

skill = Path(__file__).resolve().parents[1]
def run(*args):
    result = subprocess.run([sys.executable, str(skill / "scripts/crg.pyz"), *map(str, args)], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout

with tempfile.TemporaryDirectory(prefix="crg-skill-test-") as temp:
    workspace = Path(temp).resolve()
    # Prevent inherited user CRG settings from changing the synthetic test.
    (workspace / "crg.toml").write_text('[context_rollover]\nenabled = false\nmode = "MODE_A"\n')
    output = run("observe", "--workspace", workspace, "--session", "demo", "--thread", "thread", "--state-root", workspace / "state", "--input", skill / "references/observe-sequence.jsonl", "--scope", "total")
    state = json.loads(run("status", "--workspace", workspace, "--session", "demo", "--state-root", workspace / "state"))
    assert state["last_active_context_tokens"] == 30000, state
    assert state["thread_id"] == "thread", state
    assert state["last_turn_id"] == "four", state
    print(json.dumps({"result": "PASS", "synthetic": True, "live_desktop_test": False, "final_active_tokens": state["last_active_context_tokens"], "temporary_state_removed_on_exit": True}))
