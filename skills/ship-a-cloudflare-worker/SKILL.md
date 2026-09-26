---
name: ship-a-cloudflare-worker
description: Deploy a Cloudflare Worker through the Workers API with multipart module upload, then prove it is live byte-for-byte. Use when shipping, updating, or redeploying a Worker without wrangler, from CI, or from an agent.
license: MIT
compatibility: Python 3.8+, outbound HTTPS to api.cloudflare.com, a Cloudflare API token with Workers Scripts:Edit (plus Zone:Cache Purge if you purge cache).
metadata:
  author: dcodeu
  version: 1.0.3
---

# Ship a Cloudflare Worker

## Purpose

Deploy a Worker script to Cloudflare and prove it is live, using the Workers
API directly. No wrangler, no interactive login, no guessing. Built for agents:
every step is a command and every claim is verified afterward.

## Workflow

1. **Prepare the module.** A single `.js` file exporting
   `export default { async fetch(request, env, ctx) { ... } }`.
   Multi-file project or a static site? Bundle it first. The inline-everything
   recipe is in `references/single-file-build.md`; a starter template is in
   `assets/worker-template.js`.

2. **Deploy** with `scripts/deploy.py`:

   ```bash
   python3 scripts/deploy.py --script-name NAME --module worker.js
   ```

   Credentials come from the plugin's user config: at install time you are
   prompted for a Cloudflare API token (stored in your system keychain) and
   account ID, and the plugin exposes them to the scripts as
   `CLAUDE_PLUGIN_OPTION_CLOUDFLARE_API_TOKEN` /
   `CLAUDE_PLUGIN_OPTION_CLOUDFLARE_ACCOUNT_ID`. You can also pass them
   explicitly with `--api-token` / `--account-id`.

   This PUTs a multipart body (metadata JSON plus the module) to
   `/accounts/{account_id}/workers/scripts/{name}`. A `200` with
   `success:true` means the API accepted the upload. It does not mean the
   worker is serving your code. See `references/module-upload.md` for the
   exact request shape and error codes.

3. **Verify** with `scripts/verify.py`:

   ```bash
   python3 scripts/verify.py --script-name NAME --module worker.js \
     [--url https://<your-worker-domain> --expect-file dist.html]
   ```

   This downloads the script back from the API and compares sha256 against
   your local file. With `--url` it also fetches the public URL and compares
   the served bytes. Do not call the deploy done until every check prints
   `PASS`.

4. **Stale edge cache.** If the URL serves old bytes after a good deploy,
   purge the zone cache and re-run verify. Check every hostname separately
   (apex and www can disagree). The purge recipe is in
   `references/module-upload.md`.

## Output Contract

Report all of these, every time:
- script name and the deploy HTTP result
- sha256 match: local module vs what the API serves back
- URL byte match, if a public URL was checked
- whether a cache purge was performed

Never report "deployed" on the strength of the upload response alone.

## Operating Rules

1. The token needs Workers Scripts:Edit (and Zone:Cache Purge if you purge).
   It is supplied through the plugin's user config: prompted once at
   install, stored in the system keychain, exposed to the scripts as
   `CLAUDE_PLUGIN_OPTION_CLOUDFLARE_API_TOKEN` (or passed explicitly with
   `--api-token`). Never print the token. Never commit it. Never read it
   from ambient machine credential variables, and never ask the user to
   paste it into chat. The token is sent only to api.cloudflare.com, its
   own issuer, as a Bearer header.
2. `compatibility_date` defaults to today (`YYYY-MM-DD`). Pin an older date
   only if the worker depends on old runtime behavior.
3. Script names are per-account. Deploying to an existing name overwrites it.
   Confirm the name before touching a production worker.
4. `workers.dev` can be disabled account-wide (API error 1042 on access).
   When that happens, verify through the API round-trip or a custom domain.
5. Watch module size. The single-file recipe inlines assets as base64, which
   grows the upload about 33 percent.
