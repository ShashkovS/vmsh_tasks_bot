"""Staff consent documents. See vmshpwa/docs/admin-mcp/oauth.md."""

from html import escape

from aiohttp import web

from apps.pwa_api.branding_routes import selected_branding
from helpers.pwa.branding import PROFILES, brand_manifest
from helpers.pwa.i18n import _, current_locale

# Only responses built here receive an HTML policy in the PWA wire middleware.
CONSENT_DOCUMENT = "staff_oauth_consent_document"
CONSENT_CSP = (
    "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
    "form-action 'self'; style-src 'unsafe-inline'; img-src 'self'"
)
STYLE = """
* { box-sizing: border-box }
body { margin: 0; background: #edeff1; color: #181d21; font: 1rem/1.5 system-ui,sans-serif }
header { display: flex; align-items: center; gap: .65rem; padding: 1rem 4vw;
  border-bottom: 1px solid #d5d9dc; font-weight: 650 }
header img { width: 2rem; height: 2rem }
main { margin: clamp(1rem,8vh,5rem) auto; width: min(34rem,calc(100% - 2rem));
  padding: clamp(1.25rem,4vw,2rem); background: white; border: 1px solid #d5d9dc; border-radius: 12px }
h1 { font-size: 1.5rem; line-height: 1.25; margin: 0 }
form { display: flex; flex-wrap: wrap; gap: .75rem; margin-top: 1.5rem }
button { font: inherit; font-weight: 600; padding: .5rem 1rem; cursor: pointer;
  border-radius: .5rem; background: white; border: 1px solid #bec6cb }
button:first-child { background: #17384a; border-color: #17384a; color: white }
"""


async def document(request, title, body, *, destination=None):
    profile = PROFILES[(await selected_branding(request))["profile_id"]]
    lang = current_locale.get()
    brand = profile["englishName"] if lang == "en" else profile["name"]
    icon = brand_manifest(profile["id"], "student")["icons"][0]["src"]
    referrer = "no-referrer" if destination else "strict-origin"
    refresh = ""
    if destination:
        refresh = f'<meta http-equiv="refresh" content="0;url={escape(destination)}">'
    response = web.Response(
        text=f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="{referrer}">{refresh}<title>{escape(title)}</title>
<style>{STYLE}</style></head><body><header><img src="{escape(icon)}" alt="">
{escape(brand)}</header><main><h1>{escape(title)}</h1>{body}</main></body></html>""",
        content_type="text/html",
    )
    response[CONSENT_DOCUMENT] = True
    return response


async def consent_page(request, account):
    title = _("Подключить ChatGPT")
    body = (
        f'<p>{escape(_("Аккаунт Staff"))}: <strong>{escape(account)}</strong></p>'
        f'<p>{escape(_("Разрешить ChatGPT управлять доступными вам занятиями и читать ответы учеников?"))}</p>'
        '<form method="post">'
        f'<button name="decision" value="allow">{escape(_("Разрешить"))}</button>'
        f'<button name="decision" value="deny">{escape(_("Отказать"))}</button></form>'
    )
    return await document(request, title, body)


async def return_page(request, destination):
    # Navigate from a new document. Chromium also enforces form-action on 30x hops.
    title = _("Вернуться в ChatGPT")
    return await document(
        request, title, f'<p><a href="{escape(destination)}">{escape(title)}</a></p>',
        destination=destination,
    )
