"""Install VMSh alerts through Grafana 13.1; docs/performance/STATUS.md, 2026-10-08.

Default: read-only preflight. --apply creates paused rules, tests the stored
contact point and enables evaluation only after successful delivery. No service
restart or notification policy replacement. Existing colliding resources require
inspection instead of being overwritten. Credentials never enter logs or argv.
"""

import argparse
import base64
import copy
import json
from pathlib import Path
import re
import stat
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


FOLDER_UID = "vmsh-health"
RECEIVERS = "/apis/notifications.alerting.grafana.app/v1beta1/namespaces/default/receivers"


def load_credentials(path):
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise RuntimeError("Credentials file must be private: chmod 600 <path>")
    text = path.read_text()
    if text.lstrip().startswith("{"):
        credentials = json.loads(text)
    else:
        values = {}
        for row in text.splitlines():
            row = row.strip()
            if not row or row.startswith("#"):
                continue
            key, separator, value = row.partition("=")
            if not separator:
                raise RuntimeError("Expected key=value credentials; shell commands are not supported")
            value = value.strip()
            if len(value) > 1 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            values[key.strip()] = value
        address = urlsplit(values.get("grafanaurl", ""))
        if address.scheme != "https" or address.hostname != "grafvmsh.shashkovs.ru" or address.username:
            raise RuntimeError("Expected existing VMSh Grafana HTTPS address")
        credentials = {"grafana_user": values.get("grafanauser", ""),
                       "grafana_password": values.get("grafanapassword", ""),
                       "grafana_token": values.get("grafanatoken", ""),
                       "bot_token": values.get("tgbottoken", ""),
                       "chat_id": values.get("tgdestchatid", "")}
    if not credentials.get("grafana_token") and not (
            credentials.get("grafana_user") and credentials.get("grafana_password")):
        raise RuntimeError("Missing existing Grafana credentials")
    if not re.fullmatch(r"[0-9]{5,16}:[A-Za-z0-9_-]{20,256}", credentials.get("bot_token", "")):
        raise RuntimeError("Invalid Telegram bot token format")
    if not re.fullmatch(r"-[1-9][0-9]*", str(credentials.get("chat_id", ""))):
        raise RuntimeError("Telegram group ID must be a negative integer")
    return credentials


class ApiError(RuntimeError):
    def __init__(self, method, path, status):
        self.status = status
        super().__init__(f"Grafana {method} {path}: {status}; response body suppressed")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


class Grafana:
    def __init__(self, credentials, base="https://grafvmsh.shashkovs.ru"):
        self.base = base.rstrip("/")
        if credentials.get("grafana_token"):
            auth = "Bearer " + credentials["grafana_token"]
        else:
            login = credentials["grafana_user"] + ":" + credentials["grafana_password"]
            auth = "Basic " + base64.b64encode(login.encode()).decode()
        self.headers = {"Authorization": auth, "Content-Type": "application/json",
                        "X-Disable-Provenance": "true"}
        self.opener = build_opener(NoRedirect())

    def request(self, method, path, data=None):
        request = Request(self.base + path, method=method, headers=self.headers,
                          data=None if data is None else json.dumps(data).encode())
        try:
            with self.opener.open(request, timeout=30) as response:
                body = response.read()
                return json.loads(body) if body else None
        except HTTPError as error:
            raise ApiError(method, path, error.code) from None
        except (URLError, TimeoutError):
            raise ApiError(method, path, "network failure") from None

    def optional(self, path):
        try:
            return self.request("GET", path)
        except ApiError as error:
            if error.status == 404:
                return None
            raise


def preflight(api, template):
    if api.request("GET", "/api/org")["id"] != 1:
        raise RuntimeError("Credentials must target the existing VMSh organization 1")
    datasource = api.request("GET", "/api/datasources/uid/prometheus")
    if datasource["type"] != "prometheus":
        raise RuntimeError("Expected Prometheus datasource not found")
    existing_rules = api.request("GET", "/api/v1/provisioning/alert-rules")
    existing_points = api.request("GET", "/api/v1/provisioning/contact-points")
    group = template["groups"][0]
    desired_uids = {rule["uid"] for rule in group["rules"]}
    contact = template["contactPoints"][0]
    if any(rule["uid"] in desired_uids or
           (rule["folderUID"] == FOLDER_UID and rule["ruleGroup"] == group["name"])
           for rule in existing_rules):
        raise RuntimeError("VMSh alert rules already exist; inspect before changing them")
    if any(point["uid"] == contact["receivers"][0]["uid"] or
           point["name"] == contact["name"] for point in existing_points):
        raise RuntimeError("VMSh contact point already exists; inspect before changing it")
    folder = api.optional("/api/folders/" + FOLDER_UID)
    if folder and folder["title"] != group["folder"]:
        raise RuntimeError("Folder UID belongs to another folder")
    policies = api.request("GET", "/api/v1/provisioning/policies")
    return {"folder_exists": bool(folder), "policies": policies,
            "existing_rule_count": len(existing_rules),
            "existing_contact_count": len(existing_points)}


def test_contact(api, contact_name, integration_uid):
    receivers = api.request("GET", RECEIVERS)["items"]
    receiver = next(item for item in receivers if item["spec"]["title"] == contact_name)
    integration = next(item for item in receiver["spec"]["integrations"]
                       if item.get("uid") == integration_uid)
    # Returned integration has secureFields; Grafana decrypts its stored token.
    result = api.request("POST", RECEIVERS + "/" + quote(receiver["metadata"]["name"], safe="") + "/test", {
        "integration": integration,
        "alert": {"labels": {"alertname": "VmshAlertDeliveryTest", "severity": "info",
                             "instance": "vmsh.shashkovs.ru"},
                  "annotations": {"summary": "Проверка доставки алертов ВМШ: Telegram подключён"}},
    })
    if result.get("status") != "success":
        # Notifier errors may contain a token-bearing URL: never print them.
        raise RuntimeError("Grafana contact-point delivery test failed; rules remain paused")


def install(api, template, credentials, enable=True):
    before = preflight(api, template)
    group = template["groups"][0]
    rules = copy.deepcopy(group["rules"])
    for rule in rules:
        rule.update({"orgID": 1, "folderUID": FOLDER_UID,
                     "ruleGroup": group["name"], "isPaused": True})
    point = copy.deepcopy(template["contactPoints"][0]["receivers"][0])
    point["name"] = template["contactPoints"][0]["name"]
    if point["type"] == "telegram":
        point["settings"].update({"bottoken": credentials["bot_token"],
                                  "chatid": str(credentials["chat_id"])})
    path = "/api/v1/provisioning/folder/" + FOLDER_UID + "/rule-groups/" + quote(group["name"], safe="")
    payload = {"name": group["name"], "folderUid": FOLDER_UID, "interval": 30, "rules": rules}
    changed = False
    try:
        if not before["folder_exists"]:
            api.request("POST", "/api/folders", {"uid": FOLDER_UID, "title": group["folder"]})
        changed = True
        api.request("POST", "/api/v1/provisioning/contact-points", point)
        api.request("PUT", path, payload)
        saved = api.request("GET", path)
        if {rule["uid"] for rule in saved["rules"]} != {rule["uid"] for rule in rules}:
            raise RuntimeError("Grafana did not save the expected 13 rules")
        if not all(rule.get("isPaused") and
                   rule.get("notification_settings", {}).get("receiver") == point["name"]
                   for rule in saved["rules"]):
            raise RuntimeError("Paused state or direct notification routing did not persist")
        test_contact(api, point["name"], point["uid"])
        if enable:
            for rule in rules:
                rule["isPaused"] = False
            api.request("PUT", path, payload)
        saved = api.request("GET", path)
        if len(saved["rules"]) != len(rules) or any(rule.get("isPaused") == enable for rule in saved["rules"]):
            raise RuntimeError("Grafana rule activation verification failed")
        if api.request("GET", "/api/v1/provisioning/policies") != before["policies"]:
            raise RuntimeError("Existing notification policies changed during installation")
        return {"rules": len(saved["rules"]), "enabled": enable,
                "contact_point_test": "success", "existing_policies_preserved": True}
    except Exception:
        # Preflight proved these UIDs absent. Delete only this attempted install.
        if changed:
            cleanup_failed = False
            for rule in rules:
                try:
                    api.request("DELETE", "/api/v1/provisioning/alert-rules/" + rule["uid"])
                except ApiError as error:
                    cleanup_failed |= error.status != 404
            try:
                api.request("DELETE", "/api/v1/provisioning/contact-points/" + point["uid"])
            except ApiError as error:
                cleanup_failed |= error.status != 404
            if cleanup_failed:
                print("Cleanup incomplete; inspect VMSh rules/contact point before retrying")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    template = json.loads(Path(__file__).with_name("grafana.json").read_text())
    try:
        credentials = load_credentials(args.credentials)
        api = Grafana(credentials)
        if args.apply:
            print(json.dumps(install(api, template, credentials)))
        else:
            result = preflight(api, template)
            result.pop("policies")
            print(json.dumps({**result, "read_only": True, "planned_rules": len(template["groups"][0]["rules"])}))
    except (ApiError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
