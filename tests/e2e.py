#!/usr/bin/env python3
"""
Simple E2E test script for the Tienda API.
It performs: register -> login and validates the responses.
It uses requests if available, otherwise falls back to urllib.

Usage: python3 tests/e2e.py
"""
from __future__ import annotations
import json
import sys
import time
from urllib.parse import urljoin

BASE = "http://127.0.0.1:8000"

email = f"e2e.{int(time.time())}@example.com"
password = "Secret123!"


def print_resp(prefix: str, status: int, headers: dict, body: bytes):
    print(f"--- {prefix} ---")
    print(f"HTTP {status}")
    for k, v in headers.items():
        print(f"{k}: {v}")
    print("")
    try:
        txt = body.decode('utf-8')
    except Exception:
        txt = str(body)
    try:
        parsed = json.loads(txt)
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
    except Exception:
        print(txt)
    print("--- end ---\n")


try:
    import requests

    def post(path: str, payload: dict):
        url = urljoin(BASE, path)
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code, r.headers, r.content

except Exception:
    import urllib.request

    def post(path: str, payload: dict):
        url = urljoin(BASE, path)
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.getcode(), dict(resp.getheaders()), resp.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()


if __name__ == '__main__':
    print(f"Running E2E test against {BASE}\n")

    # Register
    status, headers, body = post('/register', {'email': email, 'password': password, 'nombre': 'E2E Bot'})
    print_resp('REGISTER', status, headers, body)
    if status not in (200, 201):
        print('Register failed; aborting E2E.', file=sys.stderr)
        sys.exit(2)

    # Login
    status, headers, body = post('/login', {'email': email, 'password': password})
    print_resp('LOGIN', status, headers, body)
    if status != 200:
        print('Login failed; aborting E2E.', file=sys.stderr)
        sys.exit(3)

    try:
        j = json.loads(body.decode('utf-8'))
    except Exception:
        print('Login response not JSON', file=sys.stderr)
        sys.exit(4)

    if 'access_token' not in j:
        print('access_token not found in login response', file=sys.stderr)
        sys.exit(5)

    print('E2E PASSED: access_token received')
    print('Token (first 80 chars):', j['access_token'][:80])

    def test_password_reset(base_url: str):
        import requests
        email = f"e2e.reset.{int(time.time())}@example.com"
        # create user
        r = requests.post(f"{base_url}/register", json={"email": email, "nombre": "E2E Reset", "password": "ResetPass123"})
        assert r.status_code == 201, r.text
        # request reset
        r2 = requests.post(f"{base_url}/request-password-reset", json={"email": email})
        assert r2.status_code == 200, r2.text
        data = r2.json()
        token = data.get('token')
        if not token:
            print('No token returned (SMTP mode); manual verification required')
            return
        # consume token
        r3 = requests.post(f"{base_url}/reset-password", json={"token": token, "new_password": "NewPass12345"})
        assert r3.status_code == 200, r3.text
        # login with new password
        r4 = requests.post(f"{base_url}/login", json={"email": email, "password": "NewPass12345"})
        assert r4.status_code == 200, r4.text
        print('Password reset E2E passed')
    sys.exit(0)
