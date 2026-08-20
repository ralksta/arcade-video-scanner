"""Unit tests for batch_controller output parsing (pure logic, no ffmpeg)."""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from batch_controller import terminal_verdict  # noqa: E402


class TestTerminalVerdict:
    """Only `>>> SUCCESS` / `>>> FAILED:` end a file. Everything else is chatter."""

    def test_success_line(self):
        assert terminal_verdict(" >>> SUCCESS! 102.1 MB (47.2%) saved in 3:11.") == \
            ("success", None)

    def test_fallback_success_line(self):
        assert terminal_verdict(" >>> SUCCESS (fallback)! 4.0 MB (14.1%) saved.")[0] == \
            "success"

    def test_failed_line_carries_the_reason(self):
        status, reason = terminal_verdict(
            " >>> FAILED: Binary search: no quality level produced acceptable results")
        assert status == "failed"
        assert reason == "Binary search: no quality level produced acceptable results"

    def test_failed_line_without_reason_gets_a_default(self):
        assert terminal_verdict(">>> FAILED")[1] == "Encoding failed"

    def test_rejected_ladder_rung_is_not_a_failure(self):
        # Regression: a run that rejects Q=55 and then succeeds at Q=45 was
        # reported as FAILED, even with the _opt.mp4 sitting on disk.
        assert terminal_verdict("    -> Quality too low for this level.") == (None, None)

    def test_aborted_pass_is_not_a_failure(self):
        assert terminal_verdict(
            " -> Size exceeded mid-encode (499.3 MB >= 498.7 MB). Aborting pass...") == \
            (None, None)

    def test_per_pass_result_is_not_a_verdict(self):
        assert terminal_verdict(" -> Result: Q=65 | Saved: 53.20% | SSIM: 0.9444") == \
            (None, None)

    def test_progress_line_is_not_a_verdict(self):
        assert terminal_verdict(
            " hevc_videotoolbox [████░░░░░░] 40% | 17.8x | 691kbits/s") == (None, None)

    def test_empty_line(self):
        assert terminal_verdict("") == (None, None)
