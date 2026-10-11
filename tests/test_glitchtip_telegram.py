"""Digest transport tests use fake webhooks and never contact Telegram."""
import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    'glitchtip_telegram', Path(__file__).resolve().parents[1] / 'docs/deploy/glitchtip/telegram-webhook.py',
)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)
PROJECTS = {'vmsh-front': {'label': 'ВМШ · frontend', 'organization': 'vmsh'}}


def test_only_fixed_organization_issue_links_leave_host():
    attachments = [{'title_link': link, 'title': 'private exception', 'text': 'private payload'}
                   for link in ['https://glitch.leaders.tech/vmsh/issues/17?token=private',
                                'https://glitch.leaders.tech/tlf/issues/18',
                                'https://glitch.leaders.tech@attacker.test/vmsh/issues/19',
                                'http://glitch.leaders.tech/vmsh/issues/20']]
    assert bridge.issue_links({'attachments': attachments}, 'vmsh') == [
        'https://glitch.leaders.tech/vmsh/issues/17',
    ]


def test_restart_deduplicates_and_batches_during_cooldown(tmp_path):
    state = tmp_path / 'state.sqlite3'
    digests = bridge.Digests(state)
    first = 'https://glitch.leaders.tech/vmsh/issues/17'
    second = 'https://glitch.leaders.tech/vmsh/issues/18'
    messages = []
    digests.enqueue('vmsh-front', [first])
    digests.deliver(PROJECTS, messages.append, now=1000)
    digests = bridge.Digests(state)
    digests.enqueue('vmsh-front', [first, second])
    digests.deliver(PROJECTS, messages.append, now=1001)
    assert len(messages) == 1
    digests.deliver(PROJECTS, messages.append, now=1900)
    assert len(messages) == 2
    assert first not in messages[1]
    assert second in messages[1]


def test_failed_delivery_preserves_queue_and_concurrent_arrivals(tmp_path):
    digests = bridge.Digests(tmp_path / 'state.sqlite3')
    first = 'https://glitch.leaders.tech/vmsh/issues/17'
    second = 'https://glitch.leaders.tech/vmsh/issues/18'
    digests.enqueue('vmsh-front', [first])

    def failed(_):
        raise RuntimeError('fake network failure')

    digests.deliver(PROJECTS, failed, now=1000)
    messages = []
    digests.deliver(PROJECTS, messages.append, now=1001)
    assert not messages

    def send_with_arrival(message):
        messages.append(message)
        digests.enqueue('vmsh-front', [second])

    digests.deliver(PROJECTS, send_with_arrival, now=1200)
    assert first in messages[0]
    digests.deliver(PROJECTS, messages.append, now=2100)
    assert second in messages[1]
