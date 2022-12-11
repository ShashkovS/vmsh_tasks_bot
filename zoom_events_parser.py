from aiohttp import web
from datetime import datetime, timedelta
from helpers.consts import *
from helpers.config import logger, config
from helpers.obj_classes import db

routes = web.RouteTableDef()
__ALL__ = ['routes']

ZOOM_AUTH = 'BAKPekpQQgW1C3S6MEP4-g'
ZOOM_ID = "3720025044"
TIMEZONE = timedelta(hours=3)


@routes.get('/tst')
async def get_tst(request):
    return web.Response(text='Yup! It works!', content_type='text/html')


def parse_json(data: dict):
    event = data['event']
    event_ts = datetime.utcfromtimestamp(data['event_ts'] / 1000) + TIMEZONE
    payload = data['payload']
    object = payload['object']
    is_circle = object['id'] == ZOOM_ID
    participant = object.get('participant', {})
    return event, event_ts, is_circle, participant


def process_event(event: str, event_ts: datetime, participant: dict):
    user_name = participant['user_name']
    if False:
        pass
    elif event == "meeting.participant_joined_waiting_room":
        db.add_to_queue_by_zoom_name(user_name)
    # elif event == "meeting.participant_joined":
    #     db.mark_joined(user_name, status=1)
    # elif event == "meeting.participant_admitted":
    #     db.mark_joined(user_name, status=1)
    # elif event == "meeting.participant_left":
    #     db.remove_from_queue(user_name)
    # elif event == "meeting.participant_joined_breakout_room":
    #     db.remove_from_queue(user_name)
    # elif event == "meeting.participant_left_breakout_room":
    #     db.remove_from_queue(user_name)
    # elif event == "meeting.participant_left_waiting_room":
    #     db.remove_from_queue(user_name)
    elif event == "meeting.ended":
        pass
    elif event == "meeting.started":
        pass


@routes.post('/zoomevents')
async def post_zoomevents(request: web.Request):
    try:
        logger.warning(str(request.headers) + ';' + str(await request.text()))
    except Exception as e:
        logger.warning(e)
    # if request.Authorization != ZOOM_AUTH:
    #     return web.Response(status=200)
    try:
        data = await request.json()
        event, event_ts, is_circle, participant = parse_json(data)
    except Exception as e:
        logger.error(e)
        return web.Response(status=400)
    if not is_circle or not participant:
        return web.Response(status=200)
    process_event(event, event_ts, participant)
    return web.Response(status=200)

# import json
# events = json.load(open(f'X:\_zoom_events.json', 'r', encoding='utf-8'))
# user_history = {}
# for data in events:
#     event, event_ts, is_circle, participant = parse_json(data)
#     if not is_circle or not participant:
#         continue
#     user_name = participant['user_name']
#     if user_name not in user_history:
#         user_history[user_name] = []
#     user_history[user_name].append(event.replace('meeting.participant_', ''))
#
# from collections import Counter
#
# user_history_v2 = {v: ', '.join(h) for v, h in user_history.items()}
# c = Counter(user_history_v2.values())
# print(c)
