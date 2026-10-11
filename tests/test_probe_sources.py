"""The probe must never print or store an API key. No network."""
from src.live import probe_sources as probe


def test_redact_masks_every_secret_and_ignores_empty_ones():
    text = "GET https://x/?api-key=abc123&k=zzz9 failed"
    assert probe.redact(text, ["abc123", "", "zzz9"]) == "GET https://x/?api-key=***&k=*** failed"


def test_emit_redacts_before_printing_and_recording(capsys):
    probe.LINES.clear()
    probe.emit("error for key SECRETVALUE", ["SECRETVALUE"])
    assert "SECRETVALUE" not in capsys.readouterr().out
    assert "SECRETVALUE" not in "".join(probe.LINES)


def test_probe_only_triggers_manually():
    from pathlib import Path

    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/probe-sources.yml").read_text()
    assert "workflow_dispatch" in workflow
    assert "schedule" not in workflow and "push:" not in workflow and "pull_request" not in workflow
    assert "contents: read" in workflow
