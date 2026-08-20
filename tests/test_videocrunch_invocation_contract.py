"""Pins the command lines Arcade builds for videocrunch.

videocrunch lives in its own repo now and evolves on its own schedule. Arcade
talks to it across a process boundary — a flag vector on argv — so nothing in
either test suite notices when the two drift apart. A renamed flag surfaces
only as an argparse error in a Terminal window the user opened by clicking
"Optimize", long after both suites went green.

These tests are one half of the pin. The other half lives in videocrunch's
tests/test_cli_contract.py, which asserts its parsers still *accept* this
vector. Together they mean a rename fails on one side or the other rather
than at encode time.

The POSIX branch is what is exercised, because that is what users run: the
route shlex-quotes the argv list into one AppleScript `do script` string, so
the test unwraps that string and shlex-splits it back into the original list.
Test paths deliberately contain no quotes or backslashes, which the batch
branch escapes a second time.
"""
import shlex
from unittest.mock import MagicMock, patch

from test_routes_files import FakeHandler

from arcade_scanner.config import config
from arcade_scanner.server.routes import files


def _argv_from_applescript(script):
    """Recover the argv list from `tell application "Terminal" ... do script "<cmd>"`."""
    marker = 'do script "'
    start = script.index(marker) + len(marker)
    end = script.rindex('"')
    return shlex.split(script[start:end])


def _capture_cmd(url, settings_patch=None):
    """Run a route and return the argv list it handed to the Terminal."""
    handler = FakeHandler(url)
    with patch("arcade_scanner.server.routes.files.sanitize_path",
               side_effect=lambda p, *a, **k: p), \
         patch("arcade_scanner.server.routes.files.os.path.exists",
               return_value=True), \
         patch("arcade_scanner.server.routes.files.IS_WIN", False), \
         patch("arcade_scanner.server.routes.files.subprocess.run") as run:
        if settings_patch is not None:
            with patch.object(config, "settings", settings_patch):
                files.handle_get(handler)
        else:
            files.handle_get(handler)
    assert run.called, "route did not launch videocrunch at all"
    argv = list(run.call_args[0][0])
    assert argv[0] == "osascript"
    return _argv_from_applescript(argv[-1])


def _flag_value(cmd, flag):
    """Value following `flag` in a `[..., '--flag', 'value', ...]` argv list."""
    assert flag in cmd, f"{flag} missing from {cmd}"
    return cmd[cmd.index(flag) + 1]


class TestSingleFileCommand:
    """/compress -> videocrunch.py FILE --port --audio-mode --video-mode --preset --codec"""

    def test_engine_path_and_file_come_first(self):
        cmd = _capture_cmd("/compress?path=/media/a.mp4")
        assert cmd[1] == config.optimizer_path
        assert cmd[2] == "/media/a.mp4", "the file must stay a positional argument"

    def test_documented_flags_are_all_present(self):
        cmd = _capture_cmd("/compress?path=/media/a.mp4")
        for flag in ("--port", "--audio-mode", "--video-mode", "--preset", "--codec"):
            assert flag in cmd, f"{flag} is no longer sent to videocrunch"

    def test_flag_values_are_ones_videocrunch_accepts(self):
        cmd = _capture_cmd("/compress?path=/media/a.mp4&audio=standard&video=copy&codec=av1")
        assert _flag_value(cmd, "--audio-mode") == "standard"
        assert _flag_value(cmd, "--video-mode") == "copy"
        assert _flag_value(cmd, "--codec") == "av1"
        assert _flag_value(cmd, "--preset") in ("fast", "balanced", "best")
        assert _flag_value(cmd, "--port").isdigit()

    def test_encoding_preset_is_passed_through(self):
        settings = MagicMock()
        settings.encoding_preset = "best"
        cmd = _capture_cmd("/compress?path=/media/a.mp4", settings_patch=settings)
        assert _flag_value(cmd, "--preset") == "best"

    def test_optional_trim_and_quality_flags(self):
        cmd = _capture_cmd("/compress?path=/media/a.mp4&ss=00:00:10&to=00:00:20&q=65")
        assert _flag_value(cmd, "--ss") == "00:00:10"
        assert _flag_value(cmd, "--to") == "00:00:20"
        assert _flag_value(cmd, "--q") == "65"

    def test_optional_flags_are_omitted_when_unset(self):
        cmd = _capture_cmd("/compress?path=/media/a.mp4")
        for flag in ("--ss", "--to", "--q"):
            assert flag not in cmd


class TestBatchCommand:
    """/batch_compress -> batch.py --files=a,b --port=N (the `=` form, not spaced)"""

    def test_uses_equals_form_for_files_and_port(self):
        cmd = _capture_cmd("/batch_compress?paths=/media/a.mp4%7C%7C%7C/media/b.mp4")
        assert cmd[1] == config.batch_path
        assert any(a.startswith("--files=") for a in cmd), f"--files= missing from {cmd}"
        assert any(a.startswith("--port=") for a in cmd), f"--port= missing from {cmd}"

    def test_files_are_comma_separated_in_one_argument(self):
        cmd = _capture_cmd("/batch_compress?paths=/media/a.mp4%7C%7C%7C/media/b.mp4")
        files_arg = next(a for a in cmd if a.startswith("--files="))
        assert files_arg == "--files=/media/a.mp4,/media/b.mp4"

    def test_port_is_numeric(self):
        cmd = _capture_cmd("/batch_compress?paths=/media/a.mp4")
        port_arg = next(a for a in cmd if a.startswith("--port="))
        assert port_arg.split("=", 1)[1].isdigit()


class TestCallbackContract:
    """videocrunch calls back with GET /api/mark_optimized?path=… when a file is done."""

    def test_route_still_exists(self):
        handler = FakeHandler("/api/mark_optimized?path=/media/a.mp4")
        with patch("arcade_scanner.server.routes.files.sanitize_path",
                   side_effect=lambda p, *a, **k: p), \
             patch("arcade_scanner.server.routes.files.os.path.exists",
                   return_value=True), \
             patch("arcade_scanner.server.routes.files.db"):
            handled = files.handle_get(handler)
        assert handled is True, "videocrunch's completion callback is no longer routed"
        assert handler.error != 404
