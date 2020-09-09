import readSettingsFromGS


class User:
    __slots__ = ['id', 'name', 'surname', 'password']

    def __init__(self, user_id, surname, name, password):
        self.id = user_id
        self.name = name
        self.surname = surname
        self.password = password


users = []


def build_user_list():
    global users
    users = []
    readSettingsFromGS.load()
    for i in readSettingsFromGS.students[1:]:
        users.append(User(*i))


def authorize(password):
    if not users:
        build_user_list()
    for user in users:
        if user.password == password:
            return user

