#!/usr/bin/env python3
"""Deploy a Cloudflare Worker via multipart module upload.

Usage:
    CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ACCOUNT_ID=... \
        python3 deploy.py --script-name NAME --module worker.js \
        [--compatibility-date YYYY-MM-DD]

PUTs a multipart body (metadata JSON + the module file) to
/accounts/{account_id}/workers/scripts/{script_name}.
Exits non-zero unless the API reports success.
"""
import argparse
import datetime
import json
import os
import sys
import urllib.request
import urllib.error


def parse_args():
    p = argparse.ArgumentParser(description="Deploy a Cloudflare Worker via the API.")
    p.add_argument("--script-name", required=True, help="Worker script name (per-account)")
    p.add_argument("--module", required=True, help="Path to the worker .js module")
    p.add_argument("--account-id", default=os.environ.get("CLOUDFLARE_ACCOUNT_ID"))
    p.add_argument("--compatibility-date", default=datetime.date.today().isoformat())
    return p.parse_args()


def main():
    args = parse_args()
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not token:
        print("error: CLOUDFLARE_API_TOKEN is not set", file=sys.stderr)
        return 1
    if not args.account_id:
        print("error: --account-id or CLOUDFLARE_ACCOUNT_ID is required", file=sys.stderr)
        return 1

    with open(args.module, "rb") as f:
        module_src = f.read()
    print(f"uploading {args.module} ({len(module_src)} bytes) as '{args.script_name}'")

    boundary = "skill-deploy-boundary"
    metadata = {"main_module": "worker.js", "compatibility_date": args.compatibility_date}

    body = b""
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="metadata"\r\n'
    body += b"Content-Type: application/json\r\n\r\n"
    body += json.dumps(metadata).encode() + b"\r\n"
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="worker.js"; filename="worker.js"\r\n'
    body += b"Content-Type: application/javascript+module\r\n\r\n"
    body += module_src + b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    url = (f"https://api.cloudflare.com/client/v4/accounts/{args.account_id}"
           f"/workers/scripts/{args.script_name}")
    req = urllib.request.Request(url, data=body, method="PUT")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read()[:500].decode("utf-8", "replace"), file=sys.stderr)
        return 1

    print(json.dumps(data.get("result", data), indent=2)[:800])
    if not data.get("success"):
        print("DEPLOY FAILED", file=sys.stderr)
        return 1
    print("DEPLOY OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
