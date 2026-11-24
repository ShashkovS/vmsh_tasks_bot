"""Metadata-only Telegram transport; docs/deploy/glitchtip/README.md.

Native GlitchTip new-issue webhooks feed a durable, bounded per-project digest.
Only fixed GlitchTip links leave this host; no exception text or user payloads.
"""
import argparse
from contextlib import contextmanager
import hashlib
import hmac
import json
import logging
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ORIGIN = 'https://glitch.leaders.tech'
COOLDOWN = 15 * 60


def issue_links(payload, organization):
    links = set()
    for attachment in payload.get('attachments', [])[:100]:
        if not isinstance(attachment, dict):
            continue
        link = attachment.get('title_link', '')
        if not isinstance(link, str):
            continue
        parsed = urllib.parse.urlsplit(link)
        if (parsed.scheme == 'https' and parsed.netloc == 'glitch.leaders.tech'
                and parsed.path.startswith('/' + organization + '/issues/')
                and parsed.path.rstrip('/').rsplit('/', 1)[-1].isdigit()):
            links.add(ORIGIN + parsed.path)
    return sorted(links)


class Digests:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS digest (project TEXT PRIMARY KEY, '
                       'last_sent REAL NOT NULL, retry_at REAL NOT NULL, failures INTEGER NOT NULL, '
                       'pending TEXT NOT NULL, seen TEXT NOT NULL)')

    @contextmanager
    def connect(self):
        # followups-20261018.md: a Connection context commits/rolls back but
        # does not close SQLite resources; this loop runs every ten seconds.
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def enqueue(self, project, links):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO digest VALUES (?,0,0,0,?,?)', (project, '[]', '[]'))
            pending, seen = db.execute('SELECT pending,seen FROM digest WHERE project=?', (project,)).fetchone()
            pending, seen = json.loads(pending), json.loads(seen)
            for link in links:
                digest = hashlib.sha256(link.encode()).hexdigest()
                if digest not in seen:
                    pending.append(link)
                    seen.append(digest)
            db.execute('UPDATE digest SET pending=?,seen=? WHERE project=?',
                       (json.dumps(pending[-100:]), json.dumps(seen[-1000:]), project))

    def deliver(self, projects, sender, now=None):
        now = time.time() if now is None else now
        with self.connect() as db:
            rows = db.execute('SELECT project,last_sent,retry_at,failures,pending FROM digest').fetchall()
        for key, last, retry, failures, pending in rows:
            links = json.loads(pending)
            if not links or key not in projects or now < max(last + COOLDOWN, retry):
                continue
            project = projects[key]
            message = (f"GlitchTip · {project['label']}\nНовых ошибок: {len(links)}\n"
                       + '\n'.join(links[:5]))
            try:
                sender(message)
            except Exception:
                # Never log a Telegram request URL: it contains the bot token.
                failures = min(failures + 1, 6)
                with self.connect() as db:
                    db.execute('UPDATE digest SET failures=?,retry_at=? WHERE project=?',
                               (failures, now + min(60 * 2 ** failures, 3600), key))
                logging.warning('Telegram delivery failed; project=%s; retry scheduled', key)
            else:
                with self.connect() as db:
                    db.execute('BEGIN IMMEDIATE')
                    queued = json.loads(db.execute('SELECT pending FROM digest WHERE project=?', (key,)).fetchone()[0])
                    remaining = [link for link in queued if link not in links]
                    db.execute('UPDATE digest SET last_sent=?,retry_at=0,failures=0,pending=? WHERE project=?',
                               (now, json.dumps(remaining), key))
                logging.info('Telegram digest delivered; project=%s; issues=%s', key, len(links))


def telegram_sender(config):
    def send(message):
        request = urllib.request.Request(
            'https://api.telegram.org/bot' + config['telegram_bot_token'] + '/sendMessage',
            data=json.dumps({'chat_id': config['chat_id'], 'text': message,
                             'disable_web_page_preview': True}).encode(),
            headers={'Content-Type': 'application/json'},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            if not json.load(response).get('ok'):
                raise RuntimeError('Telegram rejected digest')
    return send


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    digests = Digests(args.state)
    projects = config['projects']

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            matched = next((key for key, item in projects.items()
                            if hmac.compare_digest(self.path, '/_telegram/' + item['secret'])), None)
            length = self.headers.get('Content-Length', '')
            if matched is None:
                status = 404
            elif (not length.isdigit() or not 0 < int(length) <= 65536
                  or self.headers.get('Content-Type', '').split(';')[0] != 'application/json'):
                status = 400
            else:
                try:
                    payload = json.loads(self.rfile.read(int(length)))
                    links = issue_links(payload, projects[matched]['organization'])
                    digests.enqueue(matched, links)
                    status = 202
                except (ValueError, TypeError, AttributeError):
                    status = 400
            self.send_response(status)
            self.send_header('Content-Length', '0')
            self.end_headers()
            self.close_connection = True

    def worker():
        while True:
            try:
                digests.deliver(projects, telegram_sender(config))
            except Exception:
                logging.error('Digest worker failed; next pass in 10 seconds')
            time.sleep(10)

    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    threading.Thread(target=worker, daemon=True).start()
    server = HTTPServer(('127.0.0.1', 8012), Handler)
    server.timeout = 10
    server.socket.settimeout(10)
    server.serve_forever()


if __name__ == '__main__':
    main()
