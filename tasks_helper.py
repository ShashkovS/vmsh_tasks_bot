# TODO : this is shitcode
import readSettingsFromGS


class Task:
    __slots__ = ['lesson', 'name', 'point', 'short_description']

    def __init__(self, lesson: str, name: str, point: str, desc: str = ''):
        self.lesson = lesson
        self.name = name
        self.point = point
        self.short_description = desc

    def __str__(self):
        return "Задача {}.{}{} - {}".format(self.lesson, self.name, self.point, self.short_description)


class Lesson:
    __slots__ = ['number', 'tasks', 'last']

    def __init__(self, num: str, tasks: list, last: bool = False):
        self.number = num
        self.tasks = tasks
        self.last = last

    def add_task(self, task: Task):
        self.tasks.append(task)


lessons = []


def build_lesson_list():
    global lessons
    lessons = []
    readSettingsFromGS.load()
    cur_lesson = None
    for i in readSettingsFromGS.problems[1:]:
        if len(i) == 5:
            if cur_lesson:
                lessons.append(cur_lesson)
            cur_lesson = Lesson(i[0], [])
            cur_lesson.add_task(Task(*i[:-1]))
        elif len(i) == 4:
            cur_lesson.add_task(Task(*i))
    if cur_lesson:
        lessons.append(cur_lesson)
    lessons[-1].last = True


def get_all_lessons():
    if not lessons:
        build_lesson_list()
    return lessons


def get_lesson_tasks(lesson_num):
    for lesson in get_all_lessons():
        if lesson_num == lesson.number:
            return lesson.tasks


def get_task(lesson_num, task_num):
    tasks = get_lesson_tasks(lesson_num)
    for task in tasks:
        if task.name == task_num:
            return task


def get_last_lesson():
    for lesson in get_all_lessons():
        if lesson.last:
            return lesson.number
