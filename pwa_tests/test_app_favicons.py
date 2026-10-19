import json
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "vmshpwa" / "apps"


class IconLinks(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__()
        self.links: list[dict[str, str | None]] = []
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "link":
            self.links.append(dict(attrs))


def test_every_web_app_declares_an_existing_svg_favicon() -> None:
    for app in ("landing", "student", "family", "staff"):
        links = IconLinks((ROOT / app / "index.html").read_text(encoding="utf-8"))
        assert {
            "rel": "icon",
            "sizes": "any",
            "type": "image/svg+xml",
        } in links.links
        # docs/branding.md: bootstrap fills these slots from the selected
        # profile, while Vite ships both default and versioned brand assets.
        assert (ROOT / app / "public" / "icon.svg").is_file()
        for profile in json.loads(
            (ROOT.parent / "packages/contracts/src/brand-profiles.json").read_text()
        ):
            if profile["id"] != "vmsh":
                assert (
                    ROOT.parent
                    / "brands"
                    / profile["id"]
                    / f"v{profile['assetVersion']}"
                    / "icon.svg"
                ).is_file()


def test_installable_cabinets_declare_existing_apple_touch_icons() -> None:
    for app in ("student", "family"):
        links = IconLinks((ROOT / app / "index.html").read_text(encoding="utf-8"))
        assert {
            "rel": "apple-touch-icon",
        } in links.links
        assert (ROOT / app / "public" / "icon-192.png").is_file()
        for profile in json.loads(
            (ROOT.parent / "packages/contracts/src/brand-profiles.json").read_text()
        ):
            if profile["id"] != "vmsh":
                assert (
                    ROOT.parent
                    / "brands"
                    / profile["id"]
                    / f"v{profile['assetVersion']}"
                    / "icon-192.png"
                ).is_file()
