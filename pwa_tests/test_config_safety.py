import pytest

from helpers.config import Config, DATABASE_MUTABLE_CONFIG_FIELDS


def test_config_repr_redacts_known_secrets():
    config = Config(
        telegram_bot_token="telegram-secret",
        sentry_dsn="sentry-secret",
        set_admin_secret="admin-secret",
        zoom_secret_token="zoom-secret",
        conduit_import_api_token="conduit-secret",
        s3_access_key="access-secret",
        s3_secret_key="storage-secret",
        first_admin_password="first-admin-secret",
    )

    rendered = repr(config)
    for secret in (
        "telegram-secret",
        "sentry-secret",
        "admin-secret",
        "zoom-secret",
        "conduit-secret",
        "access-secret",
        "storage-secret",
        "first-admin-secret",
    ):
        assert secret not in rendered


def test_database_settings_can_only_change_feature_fields():
    config = Config(telegram_bot_token="original")
    config.update_from_dict(
        {"result_mode": "res_after_week"},
        allowed_fields=DATABASE_MUTABLE_CONFIG_FIELDS,
    )
    assert config.result_mode == "res_after_week"

    with pytest.raises(ValueError, match="cannot override"):
        config.update_from_dict(
            {"telegram_bot_token": "replacement"},
            allowed_fields=DATABASE_MUTABLE_CONFIG_FIELDS,
        )
    assert config.telegram_bot_token == "original"
