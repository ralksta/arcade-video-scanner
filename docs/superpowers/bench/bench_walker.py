"""Benchmark: os.walk + os.path.getsize (dev) vs os.scandir + entry.stat (branch idea).

Both variants implement the same semantics as the current
AsyncFileSystem._walker_worker filtering: find video files above a size
threshold, pruning excluded dirs. Synthetic tree in a tmp dir only.
"""
import os
import shutil
import statistics
import tempfile
import time

VIDEO_EXTENSIONS = frozenset({'.mp4', '.mkv', '.avi', '.mov', '.m4v'})
MIN_SIZE = 1024  # bytes; small so roughly half the files pass

N_DIRS = 300
FILES_PER_DIR = 40
DEPTH_FANOUT = 5
REPEATS = 7


def build_tree(root):
    """300 dirs x 40 files = 12k files, nested, half video / half not."""
    dirs = []
    for i in range(N_DIRS):
        # nest every DEPTH_FANOUT dirs one level deeper
        parent = root if i < DEPTH_FANOUT else dirs[i // DEPTH_FANOUT - 1]
        d = os.path.join(parent, f"dir_{i:03d}")
        os.makedirs(d, exist_ok=True)
        dirs.append(d)
        for j in range(FILES_PER_DIR):
            ext = ".mp4" if j % 2 == 0 else ".txt"
            size = 2048 if j % 4 == 0 else 512
            with open(os.path.join(d, f"file_{j:03d}{ext}"), "wb") as f:
                f.write(b"\0" * size)
    return dirs


def is_video(name):
    if name.startswith("._"):
        return False
    return os.path.splitext(name)[1].lower() in VIDEO_EXTENSIONS


def walk_variant(root, excludes):
    """Current dev approach: os.walk, then os.path.getsize per candidate."""
    found = []
    for dirpath, dirs, files in os.walk(root):
        abs_root = os.path.abspath(dirpath)
        if any(abs_root == ex or abs_root.startswith(ex + os.sep) for ex in excludes):
            dirs.clear()
            continue
        dirs[:] = [d for d in dirs
                   if os.path.abspath(os.path.join(dirpath, d)) not in excludes]
        for fn in files:
            if not is_video(fn):
                continue
            full = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(full) >= MIN_SIZE:
                    found.append(full)
            except OSError:
                pass
    return found


def scandir_variant(root, excludes):
    """Branch idea: explicit stack + os.scandir, entry.stat() for size."""
    found = []
    stack = [root]
    while stack:
        current = stack.pop()
        abs_root = os.path.abspath(current)
        if any(abs_root == ex or abs_root.startswith(ex + os.sep) for ex in excludes):
            continue
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if os.path.abspath(entry.path) not in excludes:
                                stack.append(entry.path)
                        elif entry.is_file():
                            if is_video(entry.name) and entry.stat().st_size >= MIN_SIZE:
                                found.append(entry.path)
                    except OSError:
                        continue
        except OSError:
            continue
    return found


def bench(fn, root, excludes):
    times = []
    for _ in range(REPEATS):
        t0 = time.perf_counter()
        result = fn(root, excludes)
        times.append(time.perf_counter() - t0)
    return statistics.median(times), min(times), len(result)


def main():
    tmp = tempfile.mkdtemp(prefix="bench_walker_")
    try:
        print(f"building tree in {tmp} ...")
        dirs = build_tree(tmp)
        excludes = {os.path.abspath(dirs[7]), os.path.abspath(dirs[13])}
        total = sum(len(fs) for _, _, fs in os.walk(tmp))
        print(f"tree: {len(dirs)} dirs, {total} files, {len(excludes)} exclusions\n")

        # warm the page/dentry cache so we measure CPU, not first-touch I/O
        walk_variant(tmp, excludes)
        scandir_variant(tmp, excludes)

        w_med, w_min, w_n = bench(walk_variant, tmp, excludes)
        s_med, s_min, s_n = bench(scandir_variant, tmp, excludes)

        print(f"os.walk    median {w_med*1000:7.1f} ms   best {w_min*1000:7.1f} ms   {w_n} hits")
        print(f"os.scandir median {s_med*1000:7.1f} ms   best {s_min*1000:7.1f} ms   {s_n} hits")
        delta = (w_med - s_med) / w_med * 100
        print(f"\nscandir is {delta:+.1f}% vs walk (positive = scandir faster)")
        print(f"same result set: {w_n == s_n}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
