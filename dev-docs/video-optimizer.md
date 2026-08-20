# Video Optimizer

The encoder that used to live in this repo's `scripts/` directory has moved
to its own repository: [videocrunch](https://github.com/ralksta/videocrunch), cloned as
a sibling checkout (`../videocrunch`). Arcade invokes it as a subprocess
(`config.optimizer_path` / `config.batch_path` in `arcade_scanner/config.py`,
resolved via `VIDEOCRUNCH_PATH`, with the legacy `ARCADE_OPTIMIZER_PATH` env
var still honoured) and reads its `encode_history.jsonl` to improve its own
savings estimates. If videocrunch isn't checked out, the encode routes
return a 503 with a readable message instead of crashing.

For the encoder's internals — encoder profiles, the binary search / SSIM
verification machinery, staging & atomic replace, HDR handling, and the CLI
reference — see videocrunch's
[`docs/technical-reference.md`](https://github.com/ralksta/videocrunch/blob/main/docs/technical-reference.md).

For `scripts/mac_worker.py`, which stayed in this repo because it speaks
Arcade's HTTP queue API, see [`dev-docs/mac-worker.md`](mac-worker.md).
