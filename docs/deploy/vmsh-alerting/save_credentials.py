"""Save Grafana/Telegram credentials privately; see docs/performance/STATUS.md."""

import argparse
import getpass
import json
import os
from pathlib import Path
import re


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".runtime/vmsh-alert-credentials.json"))
    args = parser.parse_args()
    grafana_user = input("Grafana admin login (blank to use an existing API token): ").strip()
    if grafana_user:
        credentials = {"grafana_user": grafana_user,
                       "grafana_password": getpass.getpass("Grafana password (hidden): ")}
        if ":" in grafana_user or not credentials["grafana_password"]:
            raise SystemExit("Invalid Grafana username or empty password")
    else:
        credentials = {"grafana_token": getpass.getpass("Existing Grafana API token (hidden): ").strip()}
        if not credentials["grafana_token"]:
            raise SystemExit("Empty Grafana API token")
    token = getpass.getpass("Telegram bot token (hidden): ").strip()
    chat_id = input("Telegram group ID (negative integer): ").strip()
    if not re.fullmatch(r"[0-9]{5,16}:[A-Za-z0-9_-]{20,256}", token):
        raise SystemExit("Invalid bot token format")
    if not re.fullmatch(r"-[1-9][0-9]*", chat_id):
        raise SystemExit("Group ID must be a negative integer")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump({**credentials, "bot_token": token, "chat_id": chat_id}, stream)
        stream.write("\n")
    print(f"Saved privately: {args.output}")
