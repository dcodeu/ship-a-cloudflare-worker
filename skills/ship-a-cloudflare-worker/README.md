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

```bash
export CLOUDFLARE_API_TOKEN=...       # needs Workers Scripts:Edit
export CLOUDFLARE_ACCOUNT_ID=...

python3 scripts/deploy.py --script-name my-worker --module worker.js
python3 scripts/verify.py --script-name my-worker --module worker.js
```

## Status

v1.0.2 — verified end-to-end twice against the live Cloudflare API: the
shipped scripts deployed a scratch worker, confirmed it byte-identical
through the API round-trip, and deleted it; an independent closed-book
agent test using only this directory did the same. The API round-trip was
additionally confirmed against a live production worker.
