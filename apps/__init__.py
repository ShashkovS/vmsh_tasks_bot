from helpers.config import config, logger

# Должен быть порядок, в котором всё инициируется
all_apps = []

if 'tg_bot' in config.apps:
    # See docs/optional-telegram-bot.md: skip before import-time bot wiring.
    if config.telegram_bot_token:
        import apps.tg_bot

        all_apps.append(tg_bot)
    else:
        logger.info("Legacy Telegram bot disabled: telegram_bot_token is empty")

if 'game_web_app' in config.apps:
    import apps.game_web_app

    all_apps.append(game_web_app)

if 'results_app' in config.apps:
    import apps.results_app

    all_apps.append(results_app)

if 'apis_app' in config.apps:
    import apps.apis_app

    all_apps.append(apis_app)

if 'pwa_app' in config.apps:
    import apps.pwa_app

    all_apps.append(pwa_app)

if 'zoom_events_parser' in config.apps:
    import apps.zoom_events_parser

    all_apps.append(zoom_events_parser)
