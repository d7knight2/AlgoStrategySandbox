#!/usr/bin/env python3
"""Generate simple PNG icons for the Safari web app (no external deps)."""

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src" / "monitoring" / "static"


def png(w: int, h: int, rgb=(15, 17, 21)) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    rows = []
    for y in range(h):
        row = bytearray([0])
        for x in range(w):
            # simple green arrow on dark bg
            cx, cy = w / 2, h / 2
            dx, dy = x - cx, y - cy
            in_shaft = abs(dx) < w * 0.12 and dy > -h * 0.05 and dy < h * 0.28
            in_head = dy < -h * 0.05 and abs(dx) < (-dy * 0.9) and dy > -h * 0.35
            if in_shaft or in_head:
                row.extend((61, 214, 140))
            else:
                row.extend(rgb)
        rows.append(bytes(row))
    raw = b"".join(rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size, name in [(180, "icon-180.png"), (192, "icon-192.png"), (512, "icon-512.png")]:
        path = OUT / name
        path.write_bytes(png(size, size))
        print("wrote", path, path.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
