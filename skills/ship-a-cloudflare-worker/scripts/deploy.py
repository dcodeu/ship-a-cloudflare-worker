#!/usr/bin/env python3
"""Deploy a Cloudflare Worker via multipart module upload.

Usage:
    python3 deploy.py --script-name NAME --module worker.js \
        [--api-token TOKEN] [--account-id ID] \
        [--compatibility-date YYYY-MM-DD]

Credentials come from the plugin's user config (prompted once at install;
the token is stored in the system keychain) and reach this script as
CLAUDE_PLUGIN_OPTION_CLOUDFLARE_API_TOKEN /
CLAUDE_PLUGIN_OPTION_CLOUDFLARE_ACCOUNT_ID, or they can be passed
explicitly with --api-token / --account-id. This script never reads
ambient machine credential variables.

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


def credential(name, flag_value):
    """Explicit flag first, then the plugin user-config channel. Never the
    machine's ambient credential environment."""
    return flag_value or os.environ.get("CLAUDE_PLUGIN_OPTION_" + name)


def parse_args():
    p = argparse.ArgumentParser(description="Deploy a Cloudflare Worker via the API.")
    p.add_argument("--script-name", required=True, help="Worker script name (per-account)")
    p.add_argument("--module", required=True, help="Path to the worker .js module")
    p.add_argument("--api-token", default=None,
                   help="Cloudflare API token (default: plugin user config)")
    p.add_argument("--account-id", default=None,
                   help="Cloudflare account ID (default: plugin user config)")
    p.add_argument("--compatibility-date", default=datetime.date.today().isoformat())
    return p.parse_args()


def main():
    args = parse_args()
    token = credential("CLOUDFLARE_API_TOKEN", args.api_token)
    if not token:
        print("error: no API token. Install this as a Claude Code plugin and "
              "enter your token when prompted (it is stored in your system "
              "keychain), or pass --api-token explicitly.", file=sys.stderr)
        return 1
    account_id = credential("CLOUDFLARE_ACCOUNT_ID", args.account_id)
    if not account_id:
        print("error: no account ID. Configure the plugin's Cloudflare "
              "account ID, or pass --account-id explicitly.", file=sys.stderr)
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

    url = (f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
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
