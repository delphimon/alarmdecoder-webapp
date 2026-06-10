from __future__ import annotations

import argparse
import asyncio
from pathlib import Path


DEFAULT_LINES = [
    '[10000001000000003A--],001,[0000000000000000],"****DISARMED****  Ready to Arm  "',
    '[00000001000000003A--],003,[0000000000000000],"FAULT ZONE 001  FRONT DOOR      "',
    '[10000001000000003A--],001,[0000000000000000],"****DISARMED****  Ready to Arm  "',
    '[01000001000000003A--],002,[0000000000000000],"ARMED ***AWAY***You may exit now"',
    '!LRR:001,602,ARMED_AWAY',
    '!RFX:0123456,80',
    '!EXP:01,FAULT',
    '!AUI:01,READY',
]


async def run_server(host: str, port: int, lines: list[str], interval: float, capture_writes: Path | None) -> None:
    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        print(f"simulator client connected: {peer}")
        read_task = asyncio.create_task(_capture_reads(reader, capture_writes))
        try:
            while not writer.is_closing():
                for line in lines:
                    writer.write(line.encode("utf-8") + b"\n")
                    await writer.drain()
                    await asyncio.sleep(interval)
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            read_task.cancel()
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle_client, host, port)
    sockets = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    print(f"AlarmDecoder ser2sock simulator listening on {sockets}")
    async with server:
        await server.serve_forever()


async def _capture_reads(reader: asyncio.StreamReader, capture_writes: Path | None) -> None:
    while True:
        data = await reader.read(1024)
        if not data:
            return
        if capture_writes:
            capture_writes.parent.mkdir(parents=True, exist_ok=True)
            with capture_writes.open("ab") as output:
                output.write(data)
        print(f"simulator received {len(data)} bytes: {data!r}")


def load_lines(path: Path | None) -> list[str]:
    if path is None:
        return DEFAULT_LINES
    return [line for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Local read/write-safe ser2sock simulator for development.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10000)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--capture-writes", type=Path)
    args = parser.parse_args()

    asyncio.run(run_server(args.host, args.port, load_lines(args.fixture), args.interval, args.capture_writes))


if __name__ == "__main__":
    main()
