# ship-a-cloudflare-worker

Deploy a Cloudflare Worker through the Workers API and prove it is live,
without wrangler. The skill is the runbook; the bundled MCP server does
the work; `references/` holds the details agents load on demand.

## Contents

- `SKILL.md` — the skill: credentials, workflow, output contract, operating rules
- `scripts/cf_mcp_server.py` — stdio MCP server: deploy, verify, delete, purge tools
- `references/module-upload.md` — exact request shape, error codes, cache purge, delete
- `references/single-file-build.md` — recipe for bundling a static site into one module
- `assets/worker-template.js` — starter worker

The server is wired in the plugin's `.mcp.json`. Credentials come from the
plugin's user config (prompted once at install; the token is kept in the
system keychain) and reach the server through the plugin host. The agent
never handles the token.

## Quick start

Install the plugin, enter your Cloudflare API token and account ID when
prompted, then have the agent use the `ship-worker` MCP tools:
`deploy_worker` to ship the module, `verify_worker` to prove it is live.

## Status

v1.0.4 — the API logic moved into a bundled MCP server so credentials flow
exclusively through the plugin's user config. v1.0.2 was verified
end-to-end twice against the live Cloudflare API: the shipped code
deployed a scratch worker, confirmed it byte-identical through the API
round-trip, and deleted it; an independent closed-book agent test using
only this directory did the same. The API round-trip was additionally
confirmed against a live production worker.
