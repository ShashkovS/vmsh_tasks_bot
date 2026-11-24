from pathlib import Path
import re


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LOADER_PATH = REPOSITORY_ROOT / "helpers" / "loader_from_google_spreadsheets.py"
INVENTORY_PATH = (
    REPOSITORY_ROOT / "vmshpwa" / "docs" / "google-loader-inventory-and-cutover.md"
)


def test_inventory_names_every_google_worksheet_and_manual_update_command():
    loader_source = LOADER_PATH.read_text(encoding="utf-8")
    inventory = INVENTORY_PATH.read_text(encoding="utf-8")

    worksheet_names = set(re.findall(r'\.worksheet\("([^"]+)"\)', loader_source))
    expected_commands = {
        "Задачи": "/update_problems",
        "Школьники": "/update_students",
        "Учителя": "/update_teachers",
        "Группы": "/update_groups",
        "_BotUIMsgs": "/update_ui_messages",
        "_BotSettings": "/update_bot_settings",
    }

    assert worksheet_names == set(expected_commands)
    for worksheet_name, command in expected_commands.items():
        assert f"`{worksheet_name}`" in inventory or f"«{worksheet_name}»" in inventory
        assert command in inventory


def test_inventory_records_non_atomic_full_update_and_credential_boundary():
    inventory = INVENTORY_PATH.read_text(encoding="utf-8")

    assert "общей транзакции" in inventory
    assert "`/update_all`" in inventory
    assert "credentials" in inventory
    assert "PWA" in inventory
