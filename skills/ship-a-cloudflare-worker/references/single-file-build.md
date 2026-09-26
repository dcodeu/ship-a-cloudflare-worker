# Single-file build recipe

Turn a static site (HTML plus JS, CSS, fonts, images) into one Worker module
with zero build tools beyond node. Proven on a 1 MB page with a dozen
inlined images and three webfonts.

## Layout

- `index.html` with placeholders where assets go, e.g. `__MOON_JS__`,
  `__IMG_hero__`, `__FONT_Body__`.
- Asset files on disk next to it (`web/hero.jpg`, `web/fonts/body.woff2`).

## Build steps

1. Read `index.html` as text.
2. For each JS module placeholder, read the `.mjs`/`.js` file and substitute
   it inline. Strip `export` keywords if the code will run in a classic
   `<script>` tag; keep them for `<script type="module">`.
3. For each image/font placeholder, substitute a data URI:
   `data:{mime};base64,{base64 of the file}`.
4. **Fail the build if any placeholder survives.** A leftover `__IMG_x__`
   in shipped HTML is a silent broken asset. Check with a loop over every
   placeholder name and throw on the first hit.
5. Wrap the finished HTML as a Worker:

   ```js
   const HTML = <JSON.stringify(html)>;
   export default {
     async fetch(request) {
       const url = new URL(request.url);
       // route extras here (images, /api/*, well-known paths)
       return new Response(HTML, {
         headers: { "content-type": "text/html;charset=utf-8" },
       });
     },
   };
   ```

   Route binary assets (share images, favicons) as separate branches that
   return decoded base64 with the right content type, instead of inlining
   them twice.

## Rules of thumb

- Base64 inflates assets ~33 percent. Keep an eye on total module size
  against the plan limit.
- One asset used twice should be served from a route, not inlined twice.
- Keep the source `index.html` and the built `worker.js` in the same repo
  so the page stays editable and the deploy stays reproducible:
  `node build.mjs && python3 scripts/deploy.py ...` is the whole pipeline.
