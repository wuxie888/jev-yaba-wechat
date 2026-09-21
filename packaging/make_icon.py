#!/usr/bin/env python3
"""Package the approved raster mascot into macOS icon sizes; no redraw or styling."""
import subprocess
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / "assets/brand/mascot-v1.png"

def main():
    if not SOURCE.is_file():
        raise SystemExit(f"Missing brand asset: {SOURCE}")
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "AppIcon.iconset")
    out.mkdir(parents=True, exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            suffix = "@2x" if scale == 2 else ""
            dest = out / f"icon_{size}x{size}{suffix}.png"
            pixels = str(size * scale)
            subprocess.run(["/usr/bin/sips", "-z", pixels, pixels, str(SOURCE), "--out", str(dest)],
                           check=True, stdout=subprocess.DEVNULL)
    print(f"Packaged mascot into {out}")

if __name__ == "__main__":
    main()
