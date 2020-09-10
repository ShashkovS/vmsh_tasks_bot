import readSettingsFromGS
from dataclasses import dataclass

@dataclass
class User:
    id: str
    surname: str
    name: str
    password: str


users = []


def build_user_list():
    global users
    users = []
    readSettingsFromGS.load()
    for i in readSettingsFromGS.students[1:]:
        users.append(User(*i))
    print(users)


def authorize(password):
    if not users:
        build_user_list()
    for user in users:
        if user.password == password:
            return user

