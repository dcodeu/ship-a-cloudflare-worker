# ship-a-cloudflare-worker

Deploy a Cloudflare Worker through the Workers API and prove it is live,
without wrangler. A Claude plugin containing one Agent Skill, verified
end-to-end against the real API.

## What it does

An agent with this skill can take a Worker module and ship it through the
plugin's bundled MCP server (no token handling on the agent's side):

1. **Deploy** — multipart module upload straight to the Workers API.
   No wrangler, no interactive login.
2. **Verify** — downloads the script back from the API and compares hashes,
   then optionally fetches the public URL and compares hashes. A `200` on
   upload is not treated as a deploy; only a passing verify is.

It also includes a recipe for bundling a whole static site into a single
Worker module (`references/single-file-build.md`) and a starter template
(`assets/worker-template.js`).

## Install

As a Claude Code plugin:

```bash
/plugin marketplace add dcodeu/ship-a-cloudflare-worker
/plugin install ship-a-cloudflare-worker
```

Or copy `skills/ship-a-cloudflare-worker/` into any Agent Skills
installation. The format is the open Agent Skills standard, so it works
across agent platforms, not just Claude.

## Quick start

Install the plugin and enter your Cloudflare API token (needs Workers
Scripts:Edit) and account ID when prompted. The token is stored in your
system keychain, never in plain text. The agent then deploys with the
`deploy_worker` MCP tool and proves it live with `verify_worker`.

See `skills/ship-a-cloudflare-worker/SKILL.md` for the full workflow.

## Proven, not promised

This skill was verified by deploying real scratch workers to a live
Cloudflare account: upload accepted, script downloaded back and confirmed
byte-identical, scratch workers deleted afterward. An independent
closed-book test (skill directory only, no outside knowledge) reproduced
the full loop. The verification notes are in the skill's README.

## License

MIT. See [LICENSE](LICENSE).
