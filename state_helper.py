START_DIALOG_STATE = 0
GETTING_USER_INFO_STATE = 1
GETTING_TASK_INFO_STATE = 2
SENDING_PHOTO_STATE = 3

GLOBAL_STATES = dict()
GLOBAL_ID = dict()


class State:
    __slots__ = ['type', 'data']

    def __init__(self, type=START_DIALOG_STATE, data=None):
        self.type = type
        self.data = data

    def set(self, type=None, data=None):
        self.type = type
        self.data = data


def set_state(user_id, value, data=None):
    GLOBAL_STATES[user_id] = GLOBAL_STATES.get(user_id, State())
    GLOBAL_STATES[user_id].set(value, data)


def set_id(user_id, pass_id):
    GLOBAL_ID[user_id] = pass_id


def get_id(user_id):
    return GLOBAL_ID[user_id]


def get_state(user_id):
    GLOBAL_STATES[user_id] = GLOBAL_STATES.get(user_id, State())
    return GLOBAL_STATES[user_id].type


def get_data(user_id):
    GLOBAL_STATES[user_id] = GLOBAL_STATES.get(user_id, State())
    return GLOBAL_STATES[user_id].data
