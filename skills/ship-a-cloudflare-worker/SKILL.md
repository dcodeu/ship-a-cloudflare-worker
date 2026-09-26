---
name: ship-a-cloudflare-worker
description: Deploy a Cloudflare Worker through the Workers API with multipart module upload, then prove it is live byte-for-byte. Use when shipping, updating, or redeploying a Worker without wrangler, from CI, or from an agent.
license: MIT
compatibility: Python 3.8+ on the plugin host, outbound HTTPS to api.cloudflare.com, a Cloudflare API token with Workers Scripts:Edit (plus Zone:Cache Purge if you purge cache).
metadata:
  author: dcodeu
  version: 1.0.4
---

# Ship a Cloudflare Worker

## Purpose

Deploy a Worker script to Cloudflare and prove it is live, using the Workers
API directly. No wrangler, no interactive login, no guessing. Built for agents:
every step is a tool call and every claim is verified afterward.

## Credentials

They were collected once, when the plugin was installed: a Cloudflare API
token (kept in your system keychain) and account ID, declared as the
plugin's user config. The plugin's MCP server receives them from the
plugin host; you never handle the token yourself.

- Do not ask the user for the token. Do not read it from the environment.
  Do not print it. Do not pass it on any command line.
- If a tool call fails with an authentication error, the plugin's stored
  credentials are missing or wrong. Tell the user to run
  `/plugin configure ship-a-cloudflare-worker` and try again.

## Workflow

The plugin registers a `ship-worker` MCP server with four tools. Use them;
do not shell out to the API yourself.

1. **Prepare the module.** A single `.js` file exporting
   `export default { async fetch(request, env, ctx) { ... } }`.
   Multi-file project or a static site? Bundle it first. The inline-everything
   recipe is in `references/single-file-build.md`; a starter template is in
   `assets/worker-template.js`.

2. **Deploy** with the `deploy_worker` tool:

   - `script_name`: per-account worker name
   - `module_base64`: base64 of the module file (read it, encode it, pass it)
   - `compatibility_date`: optional `YYYY-MM-DD`, defaults to today

   This PUTs a multipart body (metadata JSON plus the module) to
   `/accounts/{account_id}/workers/scripts/{name}`. A `PASS` means the API
   accepted the upload. It does not mean the worker is serving your code.
   See `references/module-upload.md` for the exact request shape and error
   codes.

3. **Verify** with the `verify_worker` tool:

   - `script_name`, `module_sha256`: hex sha256 of your local module file
   - `url`, `expected_sha256`: optional; the public URL and the hex sha256
     it must serve

   This downloads the script back from the API and compares sha256 against
   your local file, and with `url` it fetches the public URL and compares
   hashes. Do not call the deploy done until every check prints `PASS`.

4. **Stale edge cache.** If the URL serves old bytes after a good deploy,
   call `purge_zone_cache` with the zone ID and re-run `verify_worker`.
   Check every hostname separately (apex and www can disagree). The purge
   recipe is in `references/module-upload.md`.

5. **Clean up scratch workers** with `delete_worker` when you are done
   testing.

## Output Contract

Report all of these, every time:
- script name and the deploy result
- sha256 match: local module vs what the API serves back
- URL hash match, if a public URL was checked
- whether a cache purge was performed

Never report "deployed" on the strength of the upload response alone.

## Operating Rules

1. The token needs Workers Scripts:Edit (and Zone:Cache Purge if you purge).
   It travels only from the plugin's user config into the MCP server, which
   sends it solely to api.cloudflare.com as a Bearer header. Never expose it
   in chat, logs, or tool arguments you author yourself.
2. `compatibility_date` defaults to today (`YYYY-MM-DD`). Pin an older date
   only if the worker depends on old runtime behavior.
3. Script names are per-account. Deploying to an existing name overwrites it.
   Confirm the name before touching a production worker.
4. `workers.dev` can be disabled account-wide (API error 1042 on access).
   When that happens, verify through the API round-trip or a custom domain.
5. Watch module size. The single-file recipe inlines assets as base64, which
   grows the upload about 33 percent.
