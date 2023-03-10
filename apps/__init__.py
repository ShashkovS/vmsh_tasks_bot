import apps.tg_bot
import apps.game_web_app
import apps.results_app
import apps.zoom_events_parser

# Должен быть порядок, в котором всё инициируется
all_apps = [
    tg_bot,
    # game_web_app,
    results_app,
    # zoom_events_parser,
]
