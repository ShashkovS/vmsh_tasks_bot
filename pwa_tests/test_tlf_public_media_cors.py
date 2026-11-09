"""Verify the deployment probe catches public images blocked by browser CORS."""

import runpy
from pathlib import Path

import pytest
from aiohttp import web

from vmshpwa.scripts.storage_smoke import StorageSmokeError


DEPLOYMENT = Path(__file__).resolve().parents[1] / "docs/deploy/tlf-app"
PROBE = runpy.run_path(str(DEPLOYMENT / "s3_probe.py"))
ORIGIN = PROBE["ORIGIN"]


@pytest.mark.parametrize("allowed_origin", [ORIGIN, "*"])
async def test_public_probe_checks_origin_and_returns_readable_bytes(
    aiohttp_server, allowed_origin
):
    async def image(request):
        assert request.headers["Origin"] == ORIGIN
        return web.Response(
            body=b"<svg/>",
            content_type="image/svg+xml",
            headers={"Access-Control-Allow-Origin": allowed_origin},
        )

    app = web.Application()
    app.router.add_get("/image.svg", image)
    server = await aiohttp_server(app)
    assert await PROBE["public_get_with_cors"](str(server.make_url("/image.svg"))) == (
        200, b"<svg/>"
    )


@pytest.mark.parametrize("allowed_origin", [None, "https://other.example"])
async def test_public_probe_rejects_success_without_matching_cors(
    aiohttp_server, allowed_origin
):
    async def image(_request):
        headers = (
            {"Access-Control-Allow-Origin": allowed_origin} if allowed_origin else {}
        )
        return web.Response(body=b"<svg/>", headers=headers)

    app = web.Application()
    app.router.add_get("/image.svg", image)
    server = await aiohttp_server(app)
    with pytest.raises(StorageSmokeError, match="does not allow the app origin"):
        await PROBE["public_get_with_cors"](str(server.make_url("/image.svg")))
