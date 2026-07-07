import asyncio
import sys

async def test():
    print("STARTING TEST")
    try:
        from arcade_scanner.scanner.media_probe import MediaProbe
        probe = MediaProbe()
        res1 = await probe.get_metadata("/Users/ralfo/Downloads/-5444695758810163208.mp4")
        print("Res1:", type(res1), res1)
    except Exception as e:
        print("EXCEPTION:", e)
    
if __name__ == "__main__":
    asyncio.run(test())
