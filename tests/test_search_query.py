"""
test_search_query.py
--------------------
Contract-Tests für die gemeinsame Suchsprache (static/search_query.js).

Die Matcher-Semantik ist zusätzlich über tests/fixtures/criteria_parity.json
an Python und den TV-Client gepinnt. Hier geht es um das, was nur der Browser
hat: den Parser und die Ordner-Vorschläge im Collection-Dialog.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

HARNESS = Path(__file__).parent / "search_query_harness.js"
node = shutil.which("node")

pytestmark = pytest.mark.skipif(node is None, reason="node not on PATH")


@pytest.fixture(scope="module")
def result():
    out = subprocess.run(
        [node, str(HARNESS)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(out.stdout)


def test_terms_support_and_negation_and_quotes(result):
    terms = result["terms"]
    assert [t["value"] for t in terms] == ["web", "lena", "trailer", "/a b"]
    assert [t["negated"] for t in terms] == [False, False, True, False]
    # Nur Werte mit Pfadtrenner gelten als Pfad — „/a b" also schon.
    assert [t["isPath"] for t in terms] == [False, False, False, True]


def test_whitespace_only_stays_literal(result):
    assert result["whitespace"] is True


def test_path_matches_only_on_folder_boundaries(result):
    assert result["folderOdBoundary"] is True
    assert result["folderOdSibling"] is False


def test_umlauts_are_folded(result):
    assert result["umlaut"] is True


def test_all_terms_must_match(result):
    assert result["andTerms"] is True
    assert result["andTermsMissing"] is False


def test_minus_excludes(result):
    assert result["excluded"] is False


def test_multiple_folder_paths_are_ored(result):
    assert result["orPaths"] is True
    assert result["orPathsMiss"] is False
    # Ein zusätzlicher Begriff bleibt UND — er muss im Treffer enthalten sein.
    assert result["orPathsWithKeyword"] is True


def test_suggestions_count_the_whole_subtree(result):
    by_path = {item["path"]: item["count"] for item in result["suggestionsOd"]}
    assert by_path["/media/ralf/OD"] == 3
    assert by_path["/media/ralf/OD/ProSessions"] == 2


def test_suggestions_rank_the_folder_name_first(result):
    assert result["suggestionsPro"][0] == "/media/ralf/OD/ProSessions"


def test_suggestions_find_deep_folders(result):
    assert "/media/ralf/OD/ProSessions/Lady Sinister" in result["suggestionsLady"]


def test_empty_query_offers_the_biggest_folder(result):
    assert result["topFolderCount"] == 5


def test_paths_with_spaces_are_quoted(result):
    assert result["quoteWithSpace"] == '"/media/ralf/OD/ProSessions/Lady Sinister"'
    assert result["quotePlain"] == "/media/ralf/OD"


def test_hash_terms_are_tags_not_paths(result):
    assert result["tagTerms"] == [
        {"value": "urlaub", "isTag": True, "isPath": False, "negated": False},
        {"value": "web", "isTag": True, "isPath": False, "negated": True},
    ]


def test_tag_suggestions_count_case_insensitively(result):
    # „Urlaub" und „urlaub" sind derselbe Tag, nicht zwei Vorschläge.
    assert result["tagSuggestions"] == [
        {"type": "tag", "value": "Urlaub", "label": "#Urlaub", "count": 2},
    ]


def test_suggestion_tokens_are_quoted_when_needed(result):
    assert result["tagToken"] == '"#Lady Sinister"'
    assert result["folderToken"] == '"/media/ralf/OD/Pro Sessions"'
