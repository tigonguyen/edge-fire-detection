"""Convert a JPEG/PNG image to raw 224x224 RGB bytes for the C++ app.

Usage:  python prepare_input.py <image.jpg> [output.rgb]
"""

import sys
from PIL import Image

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <image.jpg> [output.rgb]")
        sys.exit(1)

    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) >= 3 else "test_input.rgb"

    img = Image.open(src).convert("RGB").resize((224, 224))
    with open(dst, "wb") as f:
        f.write(img.tobytes())

    print(f"{src} -> {dst}  ({224*224*3} bytes)")

if __name__ == "__main__":
    main()
