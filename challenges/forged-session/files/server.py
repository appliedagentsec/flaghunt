"""Tiny session service.

Run it with the signing secret in the environment:

    JWT_SECRET=<secret> python3 server.py [port]

  GET /             greets whoever the bearer token says you are
  GET /admin/flag   admin only

Tokens are HS256 JWTs whose payload has "sub" and "role" ("guest" or "admin").
The flag is stored sealed with the signing secret, so the service needs the
secret to start.
"""
import base64
import hashlib
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

SECRET = os.environ["JWT_SECRET"].encode()
SEALED_FLAG = "a207ea070452e56c68ab60dbb8a9a460eef853aecfb36c046404a8a60eb623"


def unseal(blob: bytes, secret: bytes) -> bytes:
    stream = b"".join(hashlib.sha256(secret + i.to_bytes(4, "big")).digest() for i in range(len(blob) // 32 + 1))
    return bytes(a ^ b for a, b in zip(blob, stream))


FLAG = unseal(bytes.fromhex(SEALED_FLAG), SECRET).decode(errors="replace")


def b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def verify(token: str):
    try:
        head, body, sig = token.split(".")
        if json.loads(b64d(head)).get("alg") != "HS256":
            return None
        good = hmac.new(SECRET, f"{head}.{body}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(good, b64d(sig)):
            return None
        return json.loads(b64d(body))
    except Exception:
        return None


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, text: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(text.encode() + b"\n")

    def do_GET(self):
        auth = self.headers.get("Authorization", "")
        claims = verify(auth[7:]) if auth.startswith("Bearer ") else None
        if claims is None:
            return self._send(401, "missing or invalid token")
        if self.path == "/":
            return self._send(200, f"hello {claims.get('sub')} (role: {claims.get('role')})")
        if self.path == "/admin/flag":
            if claims.get("role") != "admin":
                return self._send(403, "admins only")
            return self._send(200, FLAG)
        self._send(404, "not found")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
