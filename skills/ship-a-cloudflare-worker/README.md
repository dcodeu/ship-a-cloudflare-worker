# ship-a-cloudflare-worker

Deploy a Cloudflare Worker through the Workers API and prove it is live,
without wrangler. The skill is the runbook; `scripts/` does the work;
`references/` holds the details agents load on demand.

## Contents

- `SKILL.md` — the skill: workflow, output contract, operating rules
- `scripts/deploy.py` — multipart module upload via the Workers API
- `scripts/verify.py` — API round-trip hash check plus optional public URL check
- `references/module-upload.md` — exact request shape, error codes, cache purge, delete
- `references/single-file-build.md` — recipe for bundling a static site into one module
- `assets/worker-template.js` — starter worker

## Quick start

Install as a Claude Code plugin and enter your Cloudflare API token and
account ID when prompted (the token is stored in your system keychain).
Then:

```bash
python3 scripts/deploy.py --script-name my-worker --module worker.js
python3 scripts/verify.py --script-name my-worker --module worker.js
```

Outside the plugin, pass credentials explicitly:

```bash
python3 scripts/deploy.py --script-name my-worker --module worker.js \
  --api-token TOKEN --account-id ID
```

## Status

v1.0.3 — credentials now come from the plugin's user config (prompted at
install, token in the system keychain) instead of machine environment
variables. v1.0.2 was verified end-to-end twice against the live
Cloudflare API: the shipped scripts deployed a scratch worker, confirmed
it byte-identical through the API round-trip, and deleted it; an
independent closed-book agent test using only this directory did the same.
The API round-trip was additionally confirmed against a live production
worker.
