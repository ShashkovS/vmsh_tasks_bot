"""Apply PWA schema migrations as an explicit maintenance command."""

from db_methods.pwa import apply_schema_migrations
from helpers.config import config


def main() -> None:
    state = apply_schema_migrations(config.db_filename)
    print(
        f"Migrated {config.pwa_instance or config.config_name}: "
        f"{config.db_filename} ({len(state.expected)} migrations)"
    )


if __name__ == "__main__":
    main()
