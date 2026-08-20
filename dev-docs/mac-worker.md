# Remote Worker (`scripts/mac_worker.py`)

`mac_worker.py` stayed in Arcade after the encoder split ([videocrunch](https://github.com/ralksta/videocrunch))
because it speaks Arcade's HTTP encoding-queue API, not the encoder itself.
It loads the actual encoding engine from a videocrunch checkout via
`VIDEOCRUNCH_PATH` (or the legacy `ARCADE_OPTIMIZER_PATH`) — see
`config.optimizer_path` in `arcade_scanner/config.py`.

```bash
python3 scripts/mac_worker.py --server http://nas:8000 \
    --user admin --password <pw> \  # required — the queue API rejects anonymous workers
    --schedule "01:00-08:00" \      # only work in this window (overnight OK)
    --pause-on-battery              # pause while unplugged (pmset -g batt)
```

Credentials also come from `ARCADE_SERVER` / `ARCADE_USER` / `ARCADE_PASSWORD`
or a `.env` next to the script.

**Job lifecycle.** `pending → downloading → encoding → uploading → done |
failed | cancelled`. The worker claims the *oldest* pending job via
`GET /api/queue/next` (compare-and-swap in `SQLiteStore.get_next_pending`),
downloads the source, runs the encode in a per-job work directory
(`~/encoding-queue/job_<id>/`), then uploads to `POST /api/queue/upload`.

**Progress & heartbeat.** The worker POSTs progress to
`/api/queue/progress` roughly every 10s while encoding. Percentages are *per
encode pass* — the quality search restarts the bar, which is what the phase
label is for. The same call is the cancel channel: a response of
`{"cancelled": true}` stops the job.

**Recovery.** Sessions live in the server's memory, so a server restart
invalidates the worker's token — it re-authenticates automatically on the
first 401. If the worker itself dies, `get_next_pending` lazily requeues jobs
whose heartbeat is older than 15 minutes (3 attempts, then `failed`);
otherwise the row would stay "active" forever and block re-queuing that file.

**Upload handling.** The body is streamed to `.<stem>.job<id>.part` next to
the original, verified with `arcade_scanner/core/media_replace.py`
(`verify_media_integrity`: ffprobe duration + strict decode), and only then
promoted via `os.replace`. Standard mode replaces the original and rewrites
its database row; review mode moves both files into `.review/job_<id>_<stem>/`
as before. A truncated or corrupt upload fails the job and leaves the
original untouched.
