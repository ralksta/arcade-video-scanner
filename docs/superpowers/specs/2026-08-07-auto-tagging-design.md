# Auto-Tagging Rules — Design

**Date:** 2026-08-07
**Status:** Approved design, pending implementation plan

## Summary

Rule-based auto-tagging: a rule is a saved Smart-Collection-style query plus a target
tag. Rules run server-side after every scan (and on demand) and apply their tag to
matching files. An applied tag becomes a normal user tag: removing it by hand is
final — the rule never re-applies it (apply-once semantics).

Explicitly out of scope (YAGNI): rule priorities/ordering, multiple tags per rule,
synchronized tag removal when a file stops matching, TV/iOS client changes (tags
arrive there via `/api/user/data` as before).

## Data model

- New field on `UserVideoData` (`arcade_scanner/models/user.py`):
  `auto_tag_rules: List[Dict[str, Any]] = []`, persisted like `smart_collections`
  in the `users.user_data` JSON blob.

  Rule shape:

  ```json
  {
    "id": "uuid",
    "name": "GoPro-Material",
    "tag": "gopro",
    "criteria": { "...": "same schema as smart collection criteria (models/user.py _default_criteria)" },
    "enabled": true
  }
  ```

- New table in the main SQLite DB (`arcade_scanner/database/sqlite_store.py`) for
  apply-once bookkeeping — kept out of the `user_data` blob so it scales to large
  libraries:

  ```sql
  CREATE TABLE IF NOT EXISTS auto_tag_applied (
      username  TEXT NOT NULL,
      rule_id   TEXT NOT NULL,
      file_path TEXT NOT NULL,
      PRIMARY KEY (username, rule_id, file_path)
  );
  ```

  Deleting a rule deletes its rows. Deleting a media entry may leave stale rows;
  they are harmless and can be pruned by the existing cleanup path later.

## Server-side criteria evaluation

New module `arcade_scanner/core/criteria_eval.py`:

- `matches(entry: VideoEntry, criteria: dict, user_tags: list[str], favorite: bool) -> bool`
- A faithful Python port of `evaluateCollectionMatch(video, criteria)`
  (`arcade_scanner/server/static/collections.js`): include/exclude blocks
  (status, codec, tags, resolution, orientation, media_type, format), `tagLogic`
  any/all, `favorites`, `date` (any/relative/range), `size` (MB), `duration`
  (sec), `search` substring.
- Per-user fields (tags, favorite) come from `UserVideoData`, not from the global
  `media` row.

**Parity contract test:** shared JSON fixtures of `(video, criteria, expected)`
triples; one test evaluates them via `node` against `collections.js`, the same
fixtures run against the Python port. This mirrors the repo's existing JS/HTML
contract-test approach and prevents the two evaluators from drifting.

## Rule execution

`run_auto_tag_rules(username) -> dict[rule_id, int]` (module `criteria_eval.py` or a
small `core/auto_tagger.py`):

1. Load the user's enabled rules; skip users without rules.
2. For each rule: candidates = entries matching the criteria AND not present in
   `auto_tag_applied` for (username, rule_id).
3. For each candidate: merge the tag into `user.data.tags[path]` (merge, not
   replace — do NOT go through `/api/video/tags`, which replaces the whole list;
   write via `user_store` directly), insert the `auto_tag_applied` row.
4. If the target tag does not exist in `available_tags`, create it with a default
   color.
5. Persist the user once at the end (single `add_user` write), return per-rule
   counts.

## Triggers

- **Post-scan:** call the runner for all users with enabled rules at both existing
  scan completion sites: the startup background scan (`arcade_scanner/main.py`,
  after `run_scan()`) and `/api/rescan` (`arcade_scanner/server/routes/files.py`).
  Defensive: exceptions are logged and never break the scan or server startup.
- **Manual:** `POST /api/autotag/run` (session required) runs the logged-in user's
  rules against the whole library and returns `{rule_id: newly_tagged_count}`.

## API

New route file `arcade_scanner/server/routes/autotag.py`, wired like the existing
route modules; all endpoints require a session:

- `GET  /api/autotag/rules` — list the user's rules
- `POST /api/autotag/rules` — create/update/delete/toggle a rule
  (action-style body, consistent with existing tag routes)
- `POST /api/autotag/run` — run now, returns per-rule counts

## UI

- **Create — in the Query Builder** (`collections.js`): alongside "save as smart
  collection", a save mode "Tag automatisch vergeben: ___" that POSTs a rule with
  the currently built criteria.
- **Manage — Settings modal**: new "Auto-Tagging" section
  (`arcade_scanner/templates/components.py`: nav item + `content-autotagging`
  panel; header map in `static/settings.js`): rule list with enabled toggle,
  delete, and a "Jetzt ausführen" button showing a result toast.
- New element IDs and any dynamically created IDs are added to
  `tests/test_dom_contract.py` (`DYNAMIC_IDS` where applicable).

## Error handling

- Post-scan runner: catch-all with logging; a failing rule skips to the next rule.
- Run endpoint: standard error responses consistent with existing routes.
- Unknown/legacy criteria fields are ignored (same lenience as the JS evaluator).

## Testing

- Unit tests for `criteria_eval.py` covering every criteria dimension and
  include/exclude combinations.
- JS/Python parity test on shared fixtures (requires `node`, like existing
  contract tests).
- Route tests: CRUD + run, session enforcement (mirrors the recent queue-route
  auth tests).
- Apply-once semantics: tag applied, removed by user, rule re-run → not re-applied;
  rule deleted → bookkeeping rows removed.
- DOM contract tests updated for new IDs.

## CI constraints

CI runs blocking Ruff and blocking mypy: all new code must be type-annotated and
lint-clean from the start (`pyproject.toml` mypy config with pydantic plugin).
