import asyncio
import json
from arcade_scanner.config import config

async def _run_ffprobe(filepath: str):
    print("CONFIG ffprobe_path:", config.settings.ffprobe_path)
    cmd = [
        config.settings.ffprobe_path,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        filepath
    ]
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        print("STDOUT LEN:", len(stdout))
        print("STDERR LEN:", len(stderr))
        return json.loads(stdout.decode('utf-8', errors='ignore'))
    except Exception as e:
        print("FFPROBE EXCEPTION:", e)
        return {}

async def test():
    try:
        from arcade_scanner.scanner.media_probe import MediaProbe
        res = await _run_ffprobe("/Users/ralfo/Downloads/-5444695758810163208.mp4")
        print("STREAMS IN RESULT:", "streams" in res)
        probe = MediaProbe()
        final_res = await probe.get_metadata("/Users/ralfo/Downloads/-5444695758810163208.mp4")
        print("FINAL RES:", final_res)
    except Exception as e:
        print("EXCEPTION:", e)
    
if __name__ == "__main__":
    asyncio.run(test())
