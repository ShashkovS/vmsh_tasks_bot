# -*- coding: utf-8 -*-
from obj_classes import *
exit()

if __name__ == '__main__':
    print('Self test')

    db = DB('test.db')

    u1 = User(None, 1, 'н', 'name', 'surname', 'middle', 'tok1')
    u2 = User(124, 1, 'н', 'name2', 'surname2', 'middle', 'tok2')
    u3 = User(125, 1, 'н', 'name3', 'surname3', 'middle', 'tok3')
    u1upd = User(12312, 1, 'н', 'name1', 'surname1', 'middle', 'tok1')

    User = Users()
    print(User)
    print(User.by_token['tok2'])
    print(User.by_id[1])
    print(User.by_chat_id[12312])
    print(User.get_by_id(123))
    print(User.get_by_id(1))
    print(len(User))

    p1 = Problem('н', 1, 1, 'а', 'Гы', 'текст', 0, 0, r'\d+', 'ЧИСЛО!', '123', 'check_int', 'ЛОЖЬ!', 'Крутяк')
    p2 = Problem('н', 1, 1, 'б', 'Гы', 'текст', 0, 0, r'\d+', 'ЧИСЛО!', '123', 'check_int', 'ЛОЖЬ!', 'Крутяк')
    p3 = Problem('н', 1, 2, '', 'Гы', 'текст', 0, 0, r'\d+', 'ЧИСЛО!', '123', 'check_int', 'ЛОЖЬ!', 'Крутяк')
    p2upd = Problem('н', 1, 1, 'б', 'Гы', 'текст_upd', 0, 0, r'\d+', 'ЧИСЛО!', '123', 'check_int', 'ЛОЖЬ!', 'Крутяк')

    Problem = Problems()
    print(Problem)
    print(Problem.by_id[1])
    print(Problem.by_key[('н', 1, 1, 'б')])
    print(Problem.get_by_key('н', 1, 1, 'б'))
    print(Problem.get_by_key('н', 1, 1, 'бs'))
    print(len(Problem))

    Waitlist = Waitlist()
    State = States()
    for i in range(1, 15):
        Waitlist.enter(i, i)
        State.set_by_user_id(i, STATE_SENDING_SOLUTION, i)

    print('WL: add 14 people')
    wl = Waitlist.top()
    for r in wl:
        print('wl entry = ', r)
        print('user state = ', State.get_by_user_id(r['student_id']))
        Waitlist.leave(r['student_id'])
    print('States after leaving waitlist:')
    for r in wl:
        print('user state = ', State.get_by_user_id(r['student_id']))

    print('WL: new top')
    wl = Waitlist.top()
    for r in wl:
        print(r)
        Waitlist.leave(r['student_id'])

    db.disconnect()
    print('\n' * 10)
    print('self test 2')
    db, User, Problem, State, WrittenQueue, Waitlist = init_db_and_objects('dummy2')
    for user in User.all_users:
        print(user)
    for user in Problem.all_problems:
        print(user)
    db.disconnect()

    print('written queue test')
    # def insert_into_written_task_queue(self, student_id: int, problem_id: int, cur_status: int):
    # def get_written_tasks_to_check(self):
    # def upd_written_task_status(self, id: int, new_status: int):
    # def delete_from_written_task_queue(self, id: int):
    db, User, Problem, State, WrittenQueue, Waitlist = init_db_and_objects('dummy2')
    db.insert_into_written_task_queue(123, 123, 0)
    db.insert_into_written_task_queue(123, 123, 0)
    db.insert_into_written_task_queue(123, 124, 0)
    db.insert_into_written_task_queue(123, 125, 0)
    db.insert_into_written_task_queue(123, 123, 0)
    print(db.get_written_tasks_to_check(-1))
    db.upd_written_task_status(123, 125, 1)
    print(db.get_written_tasks_to_check(-1))
    print('get_written_tasks_count', db.get_written_tasks_count())
    db.delete_from_written_task_queue(123, 123)
    db.delete_from_written_task_queue(123, 124)
    db.delete_from_written_task_queue(123, 125)
    print(db.get_written_tasks_to_check(-1))

    print('written task discussion')
    # def insert_into_written_task_discussion(self, student_id: int, problem_id: int, teacher_id: int, text: str, attach_path: str):
    # def fetch_written_task_discussion(self, student_id: int, problem_id: int):
    # db.insert_into_written_task_discussion(123, 123, None, 'Привет', None)
    # db.insert_into_written_task_discussion(123, 123, None, None, '/foo/baz.txt')
    # db.insert_into_written_task_discussion(123, 123, 999, 'Ерунда', None)
    # db.insert_into_written_task_discussion(123, 123, 999, None, '/omg/img.png')
    for row in db.fetch_written_task_discussion(123, 123): print(row)

    print('written_queue')
