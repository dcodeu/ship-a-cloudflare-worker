#!/usr/bin/env python3
"""Verify a deployed Cloudflare Worker is live and byte-identical.

Usage:
    python3 verify.py --script-name NAME --module worker.js \
        [--api-token TOKEN] [--account-id ID] \
        [--url https://<your-worker-domain> --expect-file dist.html]

Credentials come from the plugin's user config (prompted once at install;
the token is stored in the system keychain) and reach this script as
CLAUDE_PLUGIN_OPTION_CLOUDFLARE_API_TOKEN /
CLAUDE_PLUGIN_OPTION_CLOUDFLARE_ACCOUNT_ID, or they can be passed
explicitly with --api-token / --account-id. This script never reads
ambient machine credential variables.

Checks:
  1. Downloads the script source back from the API and compares sha256
     with the local module file.
  2. If --url is given, fetches the URL and compares the response bytes
     with --expect-file.

Exits 0 only if every requested check passes. A passed upload without a
passed verify is not a deploy.
"""
import argparse
import hashlib
import http.client
import json
import os
import sys
import urllib.request
import urllib.error


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def credential(name, flag_value):
    """Explicit flag first, then the plugin user-config channel. Never the
    machine's ambient credential environment."""
    return flag_value or os.environ.get("CLAUDE_PLUGIN_OPTION_" + name)


def api_get(path, token, account_id):
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}{path}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read(), resp.headers.get_content_type(), \
                resp.headers.get_param("boundary")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), None, None


def extract_module(body, content_type, boundary):
    """GET on a script returns multipart framing around the module source.
    Pull out the module bytes; fall back to the raw body if it is not
    multipart."""
    if content_type != "multipart/form-data" or not boundary:
        return body
    import email
    from email import policy
    header = f'Content-Type: multipart/form-data; boundary="{boundary}"\r\n\r\n'
    msg = email.message_from_bytes(header.encode() + body, policy=policy.HTTP)
    if not msg.is_multipart():
        return body
    fallback = None
    for part in msg.iter_parts():
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        if fallback is None:
            fallback = payload
        if part.get_filename():
            return payload
    return fallback if fallback is not None else body


def main():
    p = argparse.ArgumentParser(description="Verify a deployed Cloudflare Worker.")
    p.add_argument("--script-name", required=True)
    p.add_argument("--module", required=True, help="Local module file to compare against")
    p.add_argument("--api-token", default=None,
                   help="Cloudflare API token (default: plugin user config)")
    p.add_argument("--account-id", default=None,
                   help="Cloudflare account ID (default: plugin user config)")
    p.add_argument("--url", default=None, help="Public URL to fetch and compare")
    p.add_argument("--expect-file", default=None, help="File whose bytes the URL must serve")
    args = p.parse_args()

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
    if args.url and not args.expect_file:
        print("error: --url requires --expect-file", file=sys.stderr)
        return 1

    ok = True

    with open(args.module, "rb") as f:
        local_src = f.read()
    status, remote_body, ctype, boundary = api_get(
        f"/workers/scripts/{args.script_name}", token, account_id)
    if status != 200:
        print(f"FAIL api round-trip: HTTP {status}: {remote_body[:200]!r}")
        return 1
    remote_src = extract_module(remote_body, ctype, boundary)
    if sha256(remote_src) == sha256(local_src):
        print(f"PASS api round-trip: sha256 {sha256(local_src)[:16]}... matches")
    else:
        print(f"FAIL api round-trip: local {sha256(local_src)[:16]}... "
              f"!= remote {sha256(remote_src)[:16]}...")
        ok = False

    if args.url:
        with open(args.expect_file, "rb") as f:
            expected = f.read()
        req = urllib.request.Request(args.url, headers={"User-Agent": "skill-verify/1.0"})
        served, ucode = None, None
        try:
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    served, ucode = resp.read(), resp.status
            except http.client.IncompleteRead as e:
                served, ucode = e.partial, 200
        except urllib.error.HTTPError as e:
            served, ucode = e.read(), e.code
        except Exception as e:
            print(f"FAIL url check: {args.url} -> fetch error: {type(e).__name__}: {e}")
            ok = False
        if served is not None:
            if ucode == 200 and served == expected:
                print(f"PASS url check: {args.url} serves {len(served)} expected bytes")
            else:
                print(f"FAIL url check: {args.url} -> HTTP {ucode}, {len(served)} bytes "
                      f"(expected {len(expected)})")
                ok = False

    print("VERIFY OK" if ok else "VERIFY FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
