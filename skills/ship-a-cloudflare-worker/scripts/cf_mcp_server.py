#!/usr/bin/env python3
"""Cloudflare Workers MCP server for the ship-a-cloudflare-worker plugin.

Speaks newline-delimited JSON-RPC 2.0 over stdio and exposes four tools:
deploy_worker, verify_worker, delete_worker, purge_zone_cache.

Credentials arrive as positional argv from the plugin's .mcp.json, where
the plugin host substitutes the user's ${user_config.cloudflare_api_token}
and ${user_config.cloudflare_account_id} before spawning this process.
(The token is collected once at plugin install and kept in the user's
system keychain.) This process sends the token only to api.cloudflare.com,
its own issuer, as an Authorization: Bearer header. It never prints the
token, never persists it, and never sends it anywhere else.

Invoked by the plugin host, not by hand:
    python3 cf_mcp_server.py <api-token> <account-id>

Only the Python standard library is used.
"""
import base64
import hashlib
import http.client
import json
import sys
import urllib.request
import urllib.error

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "ship-worker"
SERVER_VERSION = "1.0.4"
API_BASE = "https://api.cloudflare.com/client/v4"


def _fail_startup(message):
    sys.stderr.write("cf_mcp_server: " + message + "\n")
    sys.exit(1)


if len(sys.argv) != 3 or not sys.argv[1] or not sys.argv[2]:
    _fail_startup("expected <api-token> <account-id> from the plugin host.")
API_TOKEN = sys.argv[1]
ACCOUNT_ID = sys.argv[2]


def _api(method, path, body=None, content_type="application/json"):
    req = urllib.request.Request(API_BASE + path, data=body, method=method)
    req.add_header("Authorization", "Bearer " + API_TOKEN)
    if body is not None:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # noqa: BLE001 - network errors surface as tool errors
        raise RuntimeError("network error: %s: %s" % (type(e).__name__, e))


def _extract_module(body, content_type, boundary):
    """GET on a script returns multipart framing around the module source.
    Pull out the module bytes; fall back to the raw body if not multipart."""
    if content_type != "multipart/form-data" or not boundary:
        return body
    import email
    from email import policy
    header = 'Content-Type: multipart/form-data; boundary="%s"\r\n\r\n' % boundary
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


def tool_deploy_worker(a):
    script_name = a["script_name"]
    module_src = base64.b64decode(a["module_base64"])
    compat = a.get("compatibility_date")
    if not compat:
        import datetime
        compat = datetime.date.today().isoformat()

    boundary = "ship-worker-deploy"
    metadata = {"main_module": "worker.js", "compatibility_date": compat}
    body = b""
    body += ("--" + boundary + "\r\n").encode()
    body += b'Content-Disposition: form-data; name="metadata"\r\n'
    body += b"Content-Type: application/json\r\n\r\n"
    body += json.dumps(metadata).encode() + b"\r\n"
    body += ("--" + boundary + "\r\n").encode()
    body += b'Content-Disposition: form-data; name="worker.js"; filename="worker.js"\r\n'
    body += b"Content-Type: application/javascript+module\r\n\r\n"
    body += module_src + b"\r\n"
    body += ("--" + boundary + "--\r\n").encode()

    status, raw = _api("PUT", "/accounts/%s/workers/scripts/%s" % (ACCOUNT_ID, script_name),
                       body, "multipart/form-data; boundary=" + boundary)
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        data = {"raw": raw[:500].decode("utf-8", "replace")}
    ok = status == 200 and data.get("success") is True
    return {
        "deploy": "PASS" if ok else "FAIL",
        "http_status": status,
        "script_name": script_name,
        "module_bytes": len(module_src),
        "detail": data.get("result", data) if ok else data,
    }


def tool_verify_worker(a):
    script_name = a["script_name"]
    local_sha = a["module_sha256"]
    out = {"script_name": script_name}

    req = urllib.request.Request(
        API_BASE + "/accounts/%s/workers/scripts/%s" % (ACCOUNT_ID, script_name))
    req.add_header("Authorization", "Bearer " + API_TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status, raw = resp.status, resp.read()
            ctype = resp.headers.get_content_type()
            boundary = resp.headers.get_param("boundary")
    except urllib.error.HTTPError as e:
        status, raw, ctype, boundary = e.code, e.read(), None, None
    if status != 200:
        out["api_round_trip"] = "FAIL"
        out["error"] = "HTTP %s: %s" % (status, raw[:200].decode("utf-8", "replace"))
        return out
    remote_src = _extract_module(raw, ctype, boundary)
    remote_sha = hashlib.sha256(remote_src).hexdigest()
    out["api_round_trip"] = "PASS" if remote_sha == local_sha else "FAIL"
    out["local_sha256"] = local_sha[:16] + "..."
    out["remote_sha256"] = remote_sha[:16] + "..."

    url = a.get("url")
    if url:
        expected_sha = a.get("expected_sha256")
        if not expected_sha:
            raise ValueError("url requires expected_sha256")
        ureq = urllib.request.Request(url, headers={"User-Agent": "ship-worker/1.0"})
        served, ucode = None, None
        try:
            try:
                with urllib.request.urlopen(ureq, timeout=30) as resp:
                    served, ucode = resp.read(), resp.status
            except http.client.IncompleteRead as e:
                served, ucode = e.partial, 200
        except urllib.error.HTTPError as e:
            served, ucode = e.read(), e.code
        except Exception as e:  # noqa: BLE001
            out["url_check"] = "FAIL"
            out["url_error"] = "fetch error: %s: %s" % (type(e).__name__, e)
            return out
        got_sha = hashlib.sha256(served).hexdigest()
        out["url_check"] = "PASS" if (ucode == 200 and got_sha == expected_sha) else "FAIL"
        out["url"] = url
        out["served_bytes"] = len(served)
    return out


def tool_delete_worker(a):
    script_name = a["script_name"]
    status, raw = _api("DELETE", "/accounts/%s/workers/scripts/%s" % (ACCOUNT_ID, script_name))
    ok = status == 200
    return {"delete": "PASS" if ok else "FAIL", "http_status": status, "script_name": script_name}


def tool_purge_zone_cache(a):
    zone_id = a["zone_id"]
    status, raw = _api("POST", "/zones/%s/purge_cache" % zone_id,
                       json.dumps({"purge_everything": True}).encode())
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        data = {}
    ok = status == 200 and data.get("success") is True
    return {"purge": "PASS" if ok else "FAIL", "http_status": status, "zone_id": zone_id}


TOOLS = {
    "deploy_worker": (
        tool_deploy_worker,
        "Deploy a Cloudflare Worker module via multipart module upload. "
        "A 200/success means the API accepted the upload; it does not mean "
        "the worker is serving your code. Always follow with verify_worker.",
        {"type": "object",
         "properties": {
             "script_name": {"type": "string", "description": "Per-account worker script name"},
             "module_base64": {"type": "string", "description": "Base64 of the worker .js module"},
             "compatibility_date": {"type": "string", "description": "YYYY-MM-DD, defaults to today"},
         },
         "required": ["script_name", "module_base64"]},
    ),
    "verify_worker": (
        tool_verify_worker,
        "Prove a deployed worker is live: downloads the script back from the "
        "API and compares sha256 with the local module; optionally fetches a "
        "public URL and compares its sha256. A deploy is not done until every "
        "requested check passes.",
        {"type": "object",
         "properties": {
             "script_name": {"type": "string"},
             "module_sha256": {"type": "string", "description": "Hex sha256 of the local module file"},
             "url": {"type": "string", "description": "Public URL to fetch and compare"},
             "expected_sha256": {"type": "string", "description": "Hex sha256 the URL must serve; required with url"},
         },
         "required": ["script_name", "module_sha256"]},
    ),
    "delete_worker": (
        tool_delete_worker,
        "Delete a worker script. Used to clean up scratch workers created "
        "during verification.",
        {"type": "object",
         "properties": {"script_name": {"type": "string"}},
         "required": ["script_name"]},
    ),
    "purge_zone_cache": (
        tool_purge_zone_cache,
        "Purge everything in a zone's cache. Use when the URL serves stale "
        "bytes after a verified deploy; re-run verify_worker afterward. "
        "Check apex and www hostnames separately.",
        {"type": "object",
         "properties": {"zone_id": {"type": "string", "description": "Cloudflare zone ID"}},
         "required": ["zone_id"]},
    ),
}


def _respond(msg_id, result=None, error=None):
    payload = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def _handle(msg):
    method = msg.get("method")
    msg_id = msg.get("id")
    if method == "initialize":
        _respond(msg_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
    elif method == "notifications/initialized":
        pass
    elif method == "tools/list":
        _respond(msg_id, {"tools": [
            {"name": name, "description": desc, "inputSchema": schema}
            for name, (fn, desc, schema) in TOOLS.items()
        ]})
    elif method == "tools/call":
        params = msg.get("params", {})
        name, args = params.get("name"), params.get("arguments", {})
        if name not in TOOLS:
            _respond(msg_id, error={"code": -32602, "message": "unknown tool: %s" % name})
            return
        try:
            result = TOOLS[name][0](args)
            _respond(msg_id, {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})
        except Exception as e:  # noqa: BLE001 - tool errors are user-facing results
            _respond(msg_id, {"content": [{"type": "text",
                                           "text": json.dumps({"error": "%s: %s" % (type(e).__name__, e)})}],
                              "isError": True})
    elif msg_id is not None:
        _respond(msg_id, error={"code": -32601, "message": "method not found: %s" % method})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if not isinstance(msg, dict) or "method" not in msg:
            continue
        _handle(msg)


if __name__ == "__main__":
    main()
