# Production nginx boundary

The template serves the three applications from one TLS origin and proxies the
six exact API/WebSocket namespaces to the existing aiohttp application. It is
a deployment artifact, not a development gateway.

## Required rendering

Before installation replace every marker in `vmshpwa.conf.template`:

- `@@PUBLIC_HOST@@`: the owner-approved lowercase ASCII FQDN, without wildcard,
  scheme, port, path or trailing dot;
- `@@BACKEND_UNIX_SOCKET@@`: exact canonical absolute Gunicorn socket path;
- `@@TLS_CONFIG_FILE@@`: absolute nginx include with certificate/key and the
  site's TLS policy;
- `@@STATIC_ROOT@@`: atomic release root containing `student/`, `family/` and
  `staff/` production builds;
- `@@CSP_MEDIA_ORIGIN@@`: one exact public Hetzner media origin, without path;
- `@@CSP_SENTRY_ORIGIN@@`: one exact Sentry ingest origin or the empty string.

Wildcards, unresolved markers and client-derived values are forbidden. Install
`vmshpwa-proxy-headers.conf` as
`/etc/nginx/snippets/vmshpwa-proxy-headers.conf`. The runtime pair for the Unix
deployment is:

```text
VMSH_PWA_TRUSTED_PROXY_HOPS=1
VMSH_PWA_TRUSTED_PROXY_CIDRS=
VMSH_PWA_TRUSTED_PROXY_UNIX_SOCKETS_JSON=["/run/vmshpwa/vmshpwa.sock"]
```

The path in the JSON and the rendered upstream must be byte-for-byte equal.
Use a dedicated directory owned by the backend service and the nginx/backend
group (`0750` directory, `0660` socket); do not put it in a generally writable
directory. Merely arriving over `AF_UNIX` is never trusted by the application.

Loopback TCP is also supported for a controlled host:

```text
VMSH_PWA_TRUSTED_PROXY_HOPS=1
VMSH_PWA_TRUSTED_PROXY_CIDRS=127.0.0.1/32,::1/128
VMSH_PWA_TRUSTED_PROXY_UNIX_SOCKETS_JSON=
```

In that variant the upstream must be changed to an exact loopback endpoint and
the backend must not listen on a public interface. Unix with restrictive file
permissions is the preferred production boundary because loopback alone does
not identify which local process connected.

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

Run the following after installing the rendered files:

```text
VMSH_PWA_PUBLIC_HOST=<approved-fqdn> \
VMSH_PWA_NGINX_CONFIG=/etc/nginx/nginx.conf \
VMSH_PWA_NGINX_SITE_CONFIG=/etc/nginx/conf.d/vmshpwa.conf \
make pwa-nginx-check
```

The command first proves that the exact host is used consistently by both
`server_name` blocks, HTTPS redirect and CSP WebSocket origin, then invokes the
installed `nginx -t`.
If nginx or the config is absent, it exits non-zero and says the live proof is
unavailable; structural unit tests do not masquerade as that production proof.

## Primary references

Checked 27 July 2026:

- [nginx proxy headers and empty-value suppression](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header);
- [nginx Unix upstream syntax](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass);
- [nginx WebSocket upgrade and timeout behavior](https://nginx.org/en/docs/http/websocket.html);
- [nginx request limiting](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html);
- [aiohttp proxy warning and custom-middleware requirement](https://docs.aiohttp.org/en/stable/web_advanced.html#deploying-behind-a-proxy);
- [aiohttp transport access](https://docs.aiohttp.org/en/stable/web_reference.html#aiohttp.web.BaseRequest.transport);
- [Python 3.14 AF_UNIX and socket address semantics](https://docs.python.org/3/library/socket.html#socket-families);
- [W3C CSP `default-src` fail-closed construction](https://www.w3.org/TR/CSP3/#directive-default-src);
- [OWASP HTTP security-header guidance](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html).
