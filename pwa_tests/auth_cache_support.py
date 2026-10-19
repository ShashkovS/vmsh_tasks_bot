"""Keep scope-boundary tests independent of the owner-approved auth TTL."""

from apps.pwa_api.middleware import PWA_AUTH_STATE


def miss_auth_cache(client):
    """Force the next SQL authority read after a fixture's out-of-band grant edit.

    Production grants may lag for 15 minutes (worker-read-cache.md). Dedicated
    cache tests cover this policy; domain tests still verify the fresh boundary.
    """
    client.app[PWA_AUTH_STATE].service.invalidate_read_cache()
