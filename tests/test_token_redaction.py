"""
test_token_redaction.py
-----------------------
Sitzungs-Token dürfen nicht im Zugriffslog landen.

`<video>`-Tags können keinen `Authorization`-Header senden. `/stream` akzeptiert
den Token deshalb als Query-Parameter — bewusst, aber mit Folgen: es ist
derselbe Token wie im Cookie, also voller Kontozugriff, und Query-Strings landen
in Server-Logs, in Proxy-Logs und in Verläufen.

Der Bestand unterdrückte `/stream`-Zeilen nur dann, wenn `verbose_scanning`
ausgeschaltet war. Wer die Diagnose einschaltet — eine harmlos klingende Option
— schrieb ab dem Moment bei jedem Videoabruf ein gültiges Zugangs-Token ins
Log. Genau die Situation, in der man Logs an andere weiterreicht, um Hilfe zu
bekommen.

Maskiert wird jetzt unabhängig von jeder Einstellung.
"""
import re

import pytest

from arcade_scanner.server.api_handler import _redact_tokens

REAL_TOKEN = "a3f1" * 16   # 64 Hex-Zeichen, wie secrets.token_hex(32)


@pytest.mark.parametrize("line", [
    f"GET /stream?path=%2Fmedia%2Fa.mp4&token={REAL_TOKEN} HTTP/1.1",
    f"GET /stream?token={REAL_TOKEN}&path=%2Fmedia%2Fa.mp4 HTTP/1.1",
    f"GET /stream?token={REAL_TOKEN} HTTP/1.1",
])
def test_token_never_survives_in_the_log_line(line):
    redacted = _redact_tokens(line)
    assert REAL_TOKEN not in redacted
    assert "token=REDACTED" in redacted


def test_the_path_stays_readable():
    """Der Diagnosewert soll erhalten bleiben — nur das Geheimnis verschwindet."""
    line = f"GET /stream?path=%2Fmedia%2Furlaub.mp4&token={REAL_TOKEN} HTTP/1.1"
    redacted = _redact_tokens(line)

    assert "/stream" in redacted
    assert "urlaub.mp4" in redacted
    assert "HTTP/1.1" in redacted


def test_lines_without_a_token_are_untouched():
    line = "GET /api/videos HTTP/1.1"
    assert _redact_tokens(line) == line


def test_non_string_arguments_pass_through():
    """log_message bekommt auch Statuscodes und Größen — die dürfen nicht brechen."""
    assert _redact_tokens(200) == 200
    assert _redact_tokens(None) is None


def test_similar_parameter_names_are_not_redacted():
    """`csrf_token` oder `token_type` sind andere Parameter — nicht überschießen."""
    line = "GET /api/x?token_type=bearer HTTP/1.1"
    assert _redact_tokens(line) == line


def test_redaction_is_independent_of_the_verbosity_setting():
    """
    Der Kern des Fundes: Die Maskierung darf nicht daran hängen, ob jemand
    `verbose_scanning` eingeschaltet hat.
    """
    import inspect

    from arcade_scanner.server.api_handler import FinderHandler

    source = inspect.getsource(FinderHandler.log_message)
    redaction_line = [ln for ln in source.splitlines() if "_redact_tokens" in ln]
    assert redaction_line, "log_message maskiert nicht"

    # Die Maskierung steht in der Weitergabe an super(), nicht in einem
    # if-Zweig, der von einer Einstellung abhängt.
    assert any("super().log_message" in ln for ln in redaction_line)


def test_regex_handles_a_query_at_the_end_of_the_string():
    assert _redact_tokens(f"/stream?token={REAL_TOKEN}") == "/stream?token=REDACTED"


def test_multiple_tokens_are_all_redacted():
    line = f"/a?token={REAL_TOKEN} /b?token={REAL_TOKEN}"
    redacted = _redact_tokens(line)
    assert REAL_TOKEN not in redacted
    assert len(re.findall("REDACTED", redacted)) == 2
