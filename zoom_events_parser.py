from aiohttp import web
from datetime import datetime, timedelta
from helpers.consts import *
from helpers.config import logger, config
from helpers.obj_classes import db

routes = web.RouteTableDef()
__ALL__ = ['routes']

ZOOM_AUTH = 'BAKPekpQQgW1C3S6MEP4-g'
ZOOM_ID = "87196763644"
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
    breakout_room_uuid = object.get('breakout_room_uuid', None)
    return event, event_ts, is_circle, participant, breakout_room_uuid


def process_event(event: str, event_ts: datetime, participant: dict):
    user_name = participant['user_name']
    if False:
        pass
    elif event == "meeting.participant_joined_waiting_room":
        db.add_to_queue(user_name, event_ts, status=0)
    elif event == "meeting.participant_joined":
        db.mark_joined(user_name, status=1)
    elif event == "meeting.participant_admitted":
        db.mark_joined(user_name, status=1)
    elif event == "meeting.participant_left":
        db.remove_from_queue(user_name)
    elif event == "meeting.participant_joined_breakout_room":
        db.remove_from_queue(user_name)
    elif event == "meeting.participant_left_breakout_room":
        db.remove_from_queue(user_name)
    elif event == "meeting.participant_left_waiting_room":
        db.remove_from_queue(user_name)
    elif event == "meeting.ended":
        pass
    elif event == "meeting.started":
        pass


@routes.post('/zoomevents')
async def post_zoomevents(request: web.Request):
    # try:
    #     logger.warning(str(request.headers) + ';' + str(await request.text()))
    # except Exception as e:
    #     logger.warning(e)
    # if request.Authorization != ZOOM_AUTH:
    #     return web.Response(status=200)
    try:
        data = await request.json()
        event, event_ts, is_circle, participant, breakout_room_uuid = parse_json(data)
    except Exception as e:
        logger.error(e)
        return web.Response(status=400)
    if not is_circle or not participant:
        return web.Response(status=200)
    process_event(event, event_ts, participant)
    zoom_user_name = participant['user_name']
    zoom_user_id = participant.get('user_id', None)
    user_id = None
    db.conn.execute('''
        insert into zoom_events ( event_ts,  event,  zoom_user_name,  zoom_user_id,  breakout_room_uuid,  user_id)
                         values (:event_ts, :event, :zoom_user_name, :zoom_user_id, :breakout_room_uuid, :user_id)
    ''', locals())
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
