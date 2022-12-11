import sqlite3
from typing import List
from datetime import datetime
from Levenshtein import jaro_winkler
from helpers.consts import USER_TYPE
from bisect import bisect_left
class DB_ZOOM_QUEUE:
    conn: sqlite3.Connection


    ########этот код сейчас не работает
    # def add_to_queue(self, zoom_user_name: str, enter_ts: datetime, status: int = 0):
    #     enter_ts = enter_ts.isoformat()
    #     cur = self.conn.cursor()
    #     cur.execute("""
    #         insert into zoom_queue ( zoom_user_name,  enter_ts,  status)
    #         values                 (:zoom_user_name, :enter_ts, :status)
    #         on conflict (zoom_user_name) do update set
    #         enter_ts=min(enter_ts, excluded.enter_ts),
    #         status=excluded.status
    #     """, locals())
    #     self.conn.commit()
    #     return cur.lastrowid
    #################
    def mark_joined(self, zoom_user_name: str, status: int = 1):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE zoom_queue SET status = :status
            WHERE zoom_user_name = :zoom_user_name
        """, args)
        self.conn.commit.change_zoom_queue_table()

    def remove_from_queue(self, zoom_user_name: str):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            DELETE from zoom_queue
            where zoom_user_name = :zoom_user_name
        """, args)
        self.conn.commit()

    def get_first_from_queue(self, show_all=False):
        cur = self.conn.cursor()
        show = 150 if show_all else 15
        cur.execute("""
            select * from zoom_queue
            order by enter_ts
            limit :show
        """, {'show': show})
        rows = cur.fetchall()
        return rows

    def get_queue_count(self):
        rows = self.conn.execute('SELECT COUNT(*) cnt FROM zoom_queue').fetchone()['cnt']
        return rows if rows is not None else 0

    def find_user_id_by_zoom_username(self, name_to_find: str) -> int: #возвращаем -1 в случае неудачи
        #if user_type is not None:
        #sql = "SELECT * FROM users where type = :user_type"
        #else:
        #скобочки
        #уровень полностью
        #имя фамилия поменять местами
        #уровень в начале в конце
        def prepare_zoom_name(name: str):
            name = name.encode('utf-16', 'surrogatepass').decode('utf-16')
            name = name.lower()
            name = name.replace('_',' ')
            name = ''.join(filter(lambda x: str.isalnum(x) or (x == ' '), name))
            name = name.replace('продолжающий', 'п')
            name = name.replace('продолжающие', 'п')
            name = name.replace('продолжающая', 'п')
            name = name.replace('продолжающее', 'п')
            name = name.replace('продолжающих', 'п')
            name = name.replace('начинающий', 'н')
            name = name.replace('начинающие', 'н')
            name = name.replace('начинающая', 'н')
            name = name.replace('начинающее', 'н')
            name = name.replace('начинающих', 'н')
            name = name.replace('эксперты', 'э')
            name = name.replace('экспертка', 'э')
            name = name.replace('эксперт', 'э')
            name = name.replace('ё', 'е')

            # удалим всё, кроме букв, цифр, пробелов или точек

            # # удалим одну букву н или п, если есть. При этом стараемся не удалить букву отчества!!!
            # for i in range(len(name)):
            #     if name[i] == 'н' or name[i] == 'п' or name[i] == 'э':
            #         name.pop(i)
            #         break

            # #проверим, вдруг в начале написано н. или п. или что-то такое. Тогда это точно не отчество
            # if (name[0] in ['н.', 'п.', 'э.']):
            #     name.pop(0)

            name = str.split(name)
            name = list(filter(lambda x: x not in ['нач', 'пр', 'экс', 'нач', 'пр', 'экс','группа'],name))
            name = list(filter(lambda x: len(x) > 1, name))  # не учитываем уровень
            name = ' '.join(name)
            # name = list(filter(lambda x: len(x) > 1 or (x == 'н') or (x == 'п'),name))
            return name

        def prepare_db_name(name:str) -> str: #удалим букву отчества
            namesplit = str.split(name)
           # print (namesplit)
            if len(namesplit) <= 1:
                return name
            else:
                n = namesplit[1].replace('.','')
                if len(n) == 1: #значит у нас есть инициал
                    return namesplit[0]
                else:
                    return name
        #готовим список всех юзеров
        sql = "SELECT * FROM users"
        request = self.conn.cursor().execute(sql, locals())
        allUsers = request.fetchall()
        allUsernames = sorted(list(map(lambda x: (x['id'],(prepare_db_name(x['name']) + ' ' + x['surname']).replace(')','').replace('(','').replace('.','').lower().replace('ё','е')), allUsers)), key=lambda x: x[1])
        name_to_find = prepare_zoom_name(name_to_find)
        print (name_to_find,end=",")

        #пытаемся найти точное совпадение
        ind = bisect_left(allUsernames, name_to_find, key=lambda x: x[1])
        if ind < len(allUsernames) and allUsernames[ind][1] == name_to_find:
            return allUsernames[ind][0]

        #может, просто где-то опечатка?
        # for name in allUsernames:
        #     if jaro_winkler(name_to_find,name[1],1/10) > 0.975:
        #         return name[0]

        #может, фамилия впереди?
        name_to_find = str.split(name_to_find)
        if len(name_to_find) < 2:
            return -1
        name_to_find.append(name_to_find.pop(0))
        name_to_find = ' '.join(name_to_find)
        ind = bisect_left(allUsernames, name_to_find, key=lambda x: x[1])
        if ind < len(allUsernames) and allUsernames[ind][1] == name_to_find:
            return allUsernames[ind][0]

        #может, просто где-то опечатка?
        # for name in allUsernames:
        #     if jaro_winkler(name_to_find,name[1],1/10) > 0.975:
        #         return name[0]

        return -1

    def add_to_queue_by_id(self, user_id: int):
        cur = self.conn.cursor()
        cur.execute("""
                    insert into zoom_queue ( user_id,  status) 
                    values                 (:user_id, 1)  
                    on conflict (user_id) do nothing
                """, locals()) #если уже был такой юзер, ничего не делаем, статус 1 - только телеграм
        self.conn.commit()
        return cur.lastrowid

    def add_to_queue_by_zoom_name(self, zoom_name: str):
        user_id = self.find_user_id_by_zoom_username(zoom_name)
        #пытаемся добавить в очередь с user_id
        #TODO: добавить сообщение пользователю в телеграм
        status = (user_id > -1) if 2 else 0
        user_id = (user_id > - 1) if user_id else None
        cur = self.conn.cursor()
        cur.execute("""
                            insert into zoom_queue ( user_id, zoom_user_name, status) 
                            values                 (:user_id, :zoom_name, :status) 
                            on conflict (user_id) do update set
                            zoom_user_name = IF(zoom_user_name IS NOT NULL, zoom_user_name, excluded.zoom_user_name)
                        """, locals())  # возможно, этот человек уже добавился в телеграме, надо проверить
        self.conn.commit()

        return cur.lastrowid



