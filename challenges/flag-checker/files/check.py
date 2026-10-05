"""Flag checker. Usage: python3 check.py <flag>"""
import sys

KEY = [0x13, 0x37, 0xC0, 0xDE]
TARGET = [0xcf, 0x2a, 0xcb, 0x84, 0xff, 0x41, 0xef, 0x99, 0x01, 0x57, 0x04, 0xc0, 0x36, 0x7b, 0x1a, 0xcb, 0x2c, 0x80, 0x28, 0xe7, 0x48, 0x9b, 0x3a, 0x21, 0x91, 0xe6, 0xd8, 0xbf, 0xe3, 0x2d]


def check(candidate: str) -> bool:
    data = candidate.encode()
    if len(data) != len(TARGET):
        return False
    prev = 0x5A
    for i, b in enumerate(data):
        prev = ((b ^ KEY[i % 4]) + prev) & 0xFF
        if prev != TARGET[i]:
            return False
    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <flag>")
    print("correct!" if check(sys.argv[1]) else "wrong.")
