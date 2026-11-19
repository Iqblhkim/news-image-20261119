"""Put the bundled front page where the harness expects it.

The repository ships entry.png, the 1024 by 1024 front page for
Thursday 19 November 2026: sixty stories, three drawn panels, a
numbers strip and a dotted world map. This script moves its bytes to
the output file unchanged. It touches no network and rolls no dice,
so running it twice writes the same file twice.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLED = os.path.join(HERE, "entry.png")


def place_image():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    with open(BUNDLED, "rb") as src:
        picture = src.read()
    if not picture:
        raise SystemExit("entry.png is empty, refusing to write output")
    dest = os.path.join(out_dir, "entry.png")
    with open(dest, "wb") as dst:
        dst.write(picture)
    return 0


if __name__ == "__main__":
    raise SystemExit(place_image())
