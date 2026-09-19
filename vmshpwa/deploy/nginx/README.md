# Production nginx boundary

The template serves a public landing page and three applications from one TLS
origin and proxies the six exact API/WebSocket namespaces to the existing
aiohttp application. It is a deployment artifact, not a development gateway.

## Required rendering

Before installation replace every marker in `vmshpwa.conf.template`:

- `@@PUBLIC_HOST@@`: the owner-approved lowercase ASCII FQDN, without wildcard,
  scheme, port, path or trailing dot;
- `@@BACKEND_UNIX_SOCKET@@`: exact canonical absolute Gunicorn socket path;
- `@@TLS_CONFIG_FILE@@`: absolute nginx include with certificate/key and the
  site's TLS policy;
- `@@STATIC_ROOT@@`: atomic release root containing `landing/`, `student/`,
  `family/` and `staff/` production builds;
- `@@CSP_MEDIA_ORIGIN@@`: exact public bucket origin that appears in generated
  media URLs (for production:
  `https://d3ca76cf4cf5-images-bucket.s3.ru1.storage.beget.cloud`), without a
  path; the S3 API endpoint is not sufficient for browser CSP;
- `@@CSP_SENTRY_ORIGIN@@`: one exact Sentry ingest origin or the empty string.

Wildcards, unresolved markers and client-derived values are forbidden. Install
`vmshpwa-proxy-headers.conf` as
`/etc/nginx/snippets/vmshpwa-proxy-headers.conf`. Nginx keeps the existing Unix
socket transport:

```text
VMSH_PWA_TRUSTED_PROXY_HOPS=1
VMSH_PWA_TRUSTED_PROXY_UNIX_SOCKETS_JSON=["/web/vmsh_tasks_bot/vmshpwa/runtime/vmshpwa.sock"]
```

The path in the JSON and the rendered upstream must be byte-for-byte equal.
Keep the socket, rendered nginx source and runtime environment under the single
deployment root `/web/vmsh_tasks_bot/vmshpwa/runtime`. The socket directory is
owned by the backend service and nginx/backend group with restrictive
permissions; it is never generally writable.
Gunicorn additionally binds `127.0.0.1:8000` for local Prometheus scrapes; nginx
does not use that listener and the backend must never bind it publicly.

The proxy replaces `Forwarded` from `$remote_addr`, fixed HTTPS and `$host`, and
suppresses all incoming `X-Forwarded-*`. It never appends client input. The
application then requires one exact hop, validates the immediate TCP/Unix
transport and accepts only the configured public origin. WebSocket `Origin` is
passed unchanged and checked before upgrade.

The CSP begins with `default-src 'none'`; external media and Sentry are explicit
render-time allowances. `style-src 'unsafe-inline'` is the only initial inline
allowance because current product components use style attributes; `unsafe-eval`
is forbidden. Tightening this after an inline-style inventory does not block the
Phase-1 proxy boundary.

The public `/` entry point is served from `landing/index.html`; its hashed
assets live under `/landing/assets/`. The landing page links only to the
Student and Family cabinets. Other paths continue through their explicit
application or legacy boundaries.

The TLS server returns `404` for public `GET /metrics`. Prometheus bypasses
nginx and scrapes `http://127.0.0.1:8000/metrics`, so the unauthenticated
application endpoint remains local to the production host.

Install the rendered nginx source from the deployment root and expose it to
nginx through symlinks:

```shell
sudo ln -sfn \
  /web/vmsh_tasks_bot/vmshpwa/runtime/nginx/vmshpwa.conf \
  /etc/nginx/conf.d/vmshpwa.conf
sudo ln -sfn \
  /web/vmsh_tasks_bot/vmshpwa/runtime/nginx/vmshpwa-proxy-headers.conf \
  /etc/nginx/snippets/vmshpwa-proxy-headers.conf
```

Run the following after installing the rendered files:

```text
VMSH_PWA_PUBLIC_HOST=<approved-fqdn> \
VMSH_PWA_NGINX_CONFIG=/etc/nginx/nginx.conf \
  VMSH_PWA_NGINX_SITE_CONFIG=/web/vmsh_tasks_bot/vmshpwa/runtime/nginx/vmshpwa.conf \
make pwa-nginx-check
```

The command first proves that the exact host is used consistently by both
`server_name` blocks, HTTPS redirect and CSP WebSocket origin, then invokes the
installed `nginx -t`.
If nginx or the config is absent, it exits non-zero and says the live proof is
unavailable; structural unit tests do not masquerade as that production proof.

## Stable release entrypoint headers

`/student/sw.js` and `/family/sw.js` are stable URLs across releases. The
template therefore returns `Cache-Control: no-store` and the exact
`Service-Worker-Allowed` scope for them. Each app's stable `index.html` returns
`Cache-Control: no-cache`, so a stored shell must revalidate after an atomic
release switch. Content-hashed assets keep normal long-lived browser caching.
Other responses receive an empty map value, so nginx does not add a second
cache header to aiohttp API responses.

Both `add_header` directives deliberately stay at the same TLS-server level as
CSP, HSTS and the rest of the security set. On nginx versions using the
standard inheritance model, defining any `add_header` inside a child location
would suppress all parent `add_header` values for that location. Do not move
these directives into the Student/Family static blocks unless the complete
security-header inheritance is proven by the installed nginx version.

## Read-only post-deploy smoke

After `nginx -t`, release switch and backend startup, check the public origin
itself:

```text
make pwa-production-http-smoke \
  PWA_PRODUCTION_ORIGIN=https://<approved-fqdn> \
  PWA_PRODUCTION_INSTANCE=<expected-runtime-instance>
```

The command sends GET requests only and never reads credentials, cookies or
private content. It refuses HTTP, IP literals, ports, paths and redirects. It
checks all three health/runtime contracts, the exact instance, production-only
feature flags, API-vs-SPA routing and security headers. Student and Family also
check their manifest, audience-owned icons and stable service-worker URL with
`no-store` and exact scope. Every response is bounded to 4 MiB and each request
has a ten-second timeout.

This is a deterministic software path for the public post-deploy check, not a
substitute for running it against the owner-approved production FQDN. Login
rate limiting, authenticated WebSocket and browser installation remain
separate release gates because this smoke is deliberately read-only and
credential-free.

## Primary references

Checked 27 July 2026:

- [nginx proxy headers and empty-value suppression](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header);
- [nginx Unix upstream syntax](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass);
- [nginx WebSocket upgrade and timeout behavior](https://nginx.org/en/docs/http/websocket.html);
- [nginx request limiting](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html);
- [nginx response headers, cache expiry and inheritance](https://nginx.org/en/docs/http/ngx_http_headers_module.html);
- [aiohttp proxy warning and custom-middleware requirement](https://docs.aiohttp.org/en/stable/web_advanced.html#deploying-behind-a-proxy);
- [aiohttp transport access](https://docs.aiohttp.org/en/stable/web_reference.html#aiohttp.web.BaseRequest.transport);
- [Python 3.14 AF_UNIX and socket address semantics](https://docs.python.org/3/library/socket.html#socket-families);
- [W3C CSP `default-src` fail-closed construction](https://www.w3.org/TR/CSP3/#directive-default-src);
- [W3C Service Worker update and HTTP-cache model](https://www.w3.org/TR/service-workers/);
- [RFC 9111 `no-store` response semantics](https://www.rfc-editor.org/rfc/rfc9111.html#name-no-store);
- [OWASP HTTP security-header guidance](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html).
