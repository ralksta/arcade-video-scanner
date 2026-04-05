import asyncio
from arcade_scanner.scanner.media_probe import MediaProbe

class NoSwallowMediaProbe(MediaProbe):
    async def get_metadata(self, filepath: str):
        # We will bypass the try/except by just running the code inside it
        raw_data = await self._run_ffprobe(filepath)
        if not raw_data or "streams" not in raw_data or not raw_data["streams"]:
            return None
        video_stream = next((s for s in raw_data["streams"] if s.get("codec_type") == "video"), {})
        audio_stream = next((s for s in raw_data["streams"] if s.get("codec_type") == "audio"), {})
        fmt = raw_data.get("format", {})
        size_mb = float(fmt.get("size", 0)) / (1024 * 1024)
        duration = float(fmt.get("duration", 0))
        bitrate_bps = float(fmt.get("bit_rate", 0))
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        video_codec = video_stream.get("codec_name", "unknown")
        profile = video_stream.get("profile", "")
        pixel_format = video_stream.get("pix_fmt", "")
        level_raw = video_stream.get("level", 0)
        try:
            level = float(level_raw)
        except:
            level = 0.0
        fps_str = video_stream.get("avg_frame_rate", "0/0")
        fps = 0.0
        if "/" in fps_str:
            try:
                num, den = fps_str.split("/")
                if float(den) > 0:
                    fps = float(num) / float(den)
            except:
                pass
        else:
            try:
                fps = float(fps_str)
            except:
                pass
        audio_codec = audio_stream.get("codec_name", "unknown")
        audio_channels = int(audio_stream.get("channels", 0))
        container = fmt.get("format_name", "unknown")
        status = "OK"
        from arcade_scanner.models.video_entry import VideoEntry
        return VideoEntry(
            FilePath=filepath,
            Size_MB=round(size_mb, 2),
            Duration=round(duration, 2),
            Resolution=f"{width}x{height}",
            FPS=round(fps, 2),
            VideoCodec=video_codec,
            AudioCodec=audio_codec,
            Container=container,
            Bitrate_Mbps=round(bitrate_bps / 1000000, 2),
            Status=status,
            favorite=False,
            vaulted=False,
            tags=[]
        )

async def test():
    try:
        probe = NoSwallowMediaProbe()
        res = await probe.get_metadata("/Users/ralfo/Downloads/-5444695758810163208.mp4")
        print("SUCCESS:", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
