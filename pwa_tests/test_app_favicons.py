from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "vmshpwa" / "apps"


def test_every_web_app_declares_an_existing_svg_favicon() -> None:
    for app in ("landing", "student", "family", "staff"):
        html = (ROOT / app / "index.html").read_text(encoding="utf-8")
        assert (
            f'<link rel="icon" href="/{app}/icon.svg" sizes="any" '
            'type="image/svg+xml" />'
        ) in html
        assert (ROOT / app / "public" / "icon.svg").is_file()


def test_installable_cabinets_declare_existing_apple_touch_icons() -> None:
    for app in ("student", "family"):
        html = (ROOT / app / "index.html").read_text(encoding="utf-8")
        assert f'<link rel="apple-touch-icon" href="/{app}/icon-192.png" />' in html
        assert (ROOT / app / "public" / "icon-192.png").is_file()
