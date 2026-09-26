// Minimal worker template. Replace the fetch handler with your logic,
// save as worker.js, then deploy with scripts/deploy.py:
//
//   python3 scripts/deploy.py --script-name my-worker --module worker.js
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return new Response("ok", { headers: { "content-type": "text/plain" } });
    }

    return new Response("hello from the skill template", {
      headers: { "content-type": "text/plain;charset=utf-8" },
    });
  },
};
