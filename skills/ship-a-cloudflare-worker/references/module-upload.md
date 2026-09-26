# Multipart module upload

The Workers API accepts a script as a multipart form. This is the same call
`wrangler deploy` makes under the hood, minus the login ceremony.

## Request

```
PUT https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/scripts/{script_name}
Authorization: Bearer {token}
Content-Type: multipart/form-data; boundary={boundary}
```

Part 1, the metadata:

```
Content-Disposition: form-data; name="metadata"
Content-Type: application/json

{"main_module": "worker.js", "compatibility_date": "2026-09-25"}
```

Part 2, the module:

```
Content-Disposition: form-data; name="worker.js"; filename="worker.js"
Content-Type: application/javascript+module

<raw module bytes>
```

`compatibility_date` pins the Workers runtime behavior. Default it to today
unless the worker depends on older runtime semantics.

## Response

`{"success": true, ...}` means the API accepted the upload. It does not mean
the worker is serving your code yet. Always follow with the verify step.

## Errors worth knowing

- `10000` / auth errors: the token is missing, wrong, or lacks
  Workers Scripts:Edit.
- `1042`: `workers.dev` is disabled on this account. The upload still works,
  but the `{name}.{account}.workers.dev` URL will not. Verify through the
  API round-trip or a custom domain with a worker route.
- `409`-style conflicts are rare; script names are per-account and an upload
  to an existing name simply overwrites it.

## Cache purge (stale edge)

After a deploy, the edge can keep serving the old bytes. Purge, then re-verify:

```
POST https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache
Authorization: Bearer {token}
Content-Type: application/json

{"purge_everything": true}
```

Needs Zone:Cache Purge on the token. Get the zone id with
`GET /client/v4/zones?name=<your-zone>`. Check every hostname separately
after purging; apex and www can disagree.

## Deleting a script

```
DELETE https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/scripts/{script_name}
```

Useful for scratch workers created during testing.

## Reading a script back

```
GET https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/scripts/{script_name}
```

Returns `multipart/form-data`, not the raw source: the module bytes sit
inside a part named after the file (`worker.js`). Parse the multipart body
and compare the part payload with your local file; comparing the raw
response bytes will not match. `scripts/verify.py` does this for you.
