#!/usr/bin/env python3
"""Smoke tests: quick checks for API endpoints without Playwright.

Checks: GET /productos, GET /categorias, POST /compras (simple) and POST /checkout (simple).
Exit code 0 on success, non-zero on failure. Prints JSON responses summary.
"""
import sys
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = 'http://127.0.0.1:8000'

def req(method, path, data=None, headers=None):
    url = BASE + path
    hdrs = headers or {}
    body = None
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        hdrs['Content-Type'] = 'application/json'
    req = Request(url, data=body, headers=hdrs, method=method)
    try:
        with urlopen(req, timeout=10) as r:
            ct = r.headers.get('content-type','')
            text = r.read().decode('utf-8')
            if 'application/json' in ct:
                return r.status, json.loads(text)
            return r.status, text
    except HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8'))
        except Exception:
            return e.code, str(e)
    except URLError as e:
        print('Request error:', e, file=sys.stderr)
        return None, str(e)

def check_get(path):
    st, body = req('GET', path)
    print(f'GET {path} ->', st)
    return st, body

def check_post(path, payload):
    st, body = req('POST', path, data=payload)
    print(f'POST {path} ->', st)
    return st, body

def main():
    ok = True
    # /productos
    st, body = check_get('/productos')
    if st != 200:
        ok = False

    # /categorias
    st, body = check_get('/categorias')
    if st != 200:
        ok = False

    # attempt a compra (may fail if DB constraints) - expect 201 or 4xx
    st, body = check_post('/compras', {'producto_id': 1, 'cantidad': 1})
    if st not in (200,201,400,404,409):
        ok = False

    # attempt checkout minimal payload
    payload = {
        'customer_name': 'Tester',
        'customer_email': 'test@example.com',
        'items': [{'producto_id': 1, 'cantidad': 1}]
    }
    st, body = check_post('/checkout', payload)
    if st not in (200,201,400,404,409):
        ok = False

    if not ok:
        print('\nSmoke tests: some checks failed')
        sys.exit(2)
    print('\nSmoke tests: OK')
    sys.exit(0)

if __name__ == '__main__':
    main()
