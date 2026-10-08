"""Initialize identity on the empty clone before first-admin startup (README.md)."""

from db_methods.pwa import PwaConnectionFactory
from db_methods.pwa.branding import get_branding, update_branding
from helpers.config import config

factory = PwaConnectionFactory(config.db_filename)
brand = factory.run_read(get_branding)
if brand["profile_id"] != "tlf-prep-clubs" or brand["default_locale"] != "en":
    assert factory.run_write(
        lambda connection: update_branding(
            connection,
            profile_id="tlf-prep-clubs",
            default_locale="en",
            expected_version=brand["version"],
        )
    )
print("Identity initialized:", factory.run_read(get_branding))
