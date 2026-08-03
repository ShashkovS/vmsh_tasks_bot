# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from pyexpat import features
from typing import List

from helpers.consts import *
from helpers.config import config, logger
from helpers.features import SYNONYMS_MODE, FEATURES
from helpers.loader_from_google_spreadsheets import google_spreadsheet_loader
import db_methods as db
from .state import State
from .user import User
from .problem import Problem


class GoogleBulkUpdateDisabled(RuntimeError):
    """Raised before the unsafe six-sheet import after a partial cutover."""


class FromGoogleSpreadsheet:
    @staticmethod
    def _normalize_sheet_text(value: str):
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        # Google Sheets/CSV exports sometimes double-escape quotes as "".
        return text.replace('""', '"')

    @staticmethod
    def update_all() -> List[str]:
        # A partial Staff cutover makes this non-transactional composition
        # destructive.  Keep recovery explicit through the individual
        # update_* methods; see google-loader-inventory-and-cutover.md.
        if not config.allow_google_update_all:
            raise GoogleBulkUpdateDisabled
        groups, problems, students, teachers, ui_messages, bot_settings = google_spreadsheet_loader.get_all_from_spreadsheet()
        errors = []
        errors += FromGoogleSpreadsheet.groups_to_db(groups)
        errors += FromGoogleSpreadsheet.problems_to_db(problems)
        FromGoogleSpreadsheet.students_to_db(students)
        FromGoogleSpreadsheet.teachers_to_db(teachers)
        FromGoogleSpreadsheet.ui_messages_to_db(ui_messages)
        FromGoogleSpreadsheet.bot_settings_to_db(bot_settings)
        return errors

    @staticmethod
    def update_problems() -> List[str]:
        problems = google_spreadsheet_loader.get_problems()
        errors = FromGoogleSpreadsheet.problems_to_db(problems)
        return errors

    @staticmethod
    def update_students():
        students = google_spreadsheet_loader.get_students()
        FromGoogleSpreadsheet.students_to_db(students)

    @staticmethod
    def update_teachers():
        teachers = google_spreadsheet_loader.get_teachers()
        FromGoogleSpreadsheet.teachers_to_db(teachers)

    @staticmethod
    def update_ui_messages():
        ui_messages = google_spreadsheet_loader.get_ui_messages()
        FromGoogleSpreadsheet.ui_messages_to_db(ui_messages)

    @staticmethod
    def update_bot_settings():
        bot_settings = google_spreadsheet_loader.get_bot_settings()
        FromGoogleSpreadsheet.bot_settings_to_db(bot_settings)

    @staticmethod
    def update_groups() -> List[str]:
        groups = google_spreadsheet_loader.get_groups()
        return FromGoogleSpreadsheet.groups_to_db(groups)

    @staticmethod
    def _normalize_allowed_groups(allowed_groups: str):
        if allowed_groups is None:
            return None
        allowed_groups = str(allowed_groups).strip()
        if not allowed_groups:
            return None
        parts = [part.strip() for part in allowed_groups.split(';') if part.strip()]
        if not parts:
            return None
        unique_parts = []
        seen = set()
        for part in parts:
            if part in seen:
                continue
            seen.add(part)
            unique_parts.append(part)
        return ';' + ';'.join(unique_parts) + ';'

    @staticmethod
    def _pick_user_group_id(group_id: str, allowed_groups: str):
        group_id = (group_id or '').strip() or None
        if group_id and ';' in group_id:
            logger.warning('Invalid group_id: %s', group_id)
            group_id = None
        if not allowed_groups:
            return group_id
        allowed_list = [part for part in allowed_groups.split(';') if part]
        if not allowed_list:
            return group_id
        if group_id in allowed_list:
            return group_id
        if group_id and group_id not in allowed_list:
            logger.warning('group_id %s is not in allowed_groups %s, using first allowed group', group_id, allowed_groups)
        return allowed_list[0]

    @staticmethod
    def _parse_bool(value: str, default: int, field_name: str, errors: List[str]) -> int:
        if value is None:
            return default
        raw = str(value).strip().lower()
        if raw == '':
            return default
        if raw in ('1', 'true', 'yes', 'y', 'да', 'on'):
            return 1
        if raw in ('0', 'false', 'no', 'n', 'нет', 'off'):
            return 0
        errors.append(f'Кривое значение "{value}" для поля "{field_name}"')
        return default

    @staticmethod
    def _parse_int(value: str, default: int, field_name: str, errors: List[str]) -> int:
        if value is None:
            return default
        raw = str(value).strip()
        if raw == '':
            return default
        try:
            return int(raw)
        except ValueError:
            errors.append(f'Кривое значение "{value}" для поля "{field_name}"')
            return default

    @staticmethod
    def _parse_float(value: str, default: float, field_name: str, errors: List[str]) -> float:
        if value is None:
            return default
        raw = str(value).strip().replace(',', '.')
        if raw == '':
            return default
        try:
            return float(raw)
        except ValueError:
            errors.append(f'Кривое значение "{value}" для поля "{field_name}"')
            return default

    @staticmethod
    def _normalize_group_row(group: dict):
        errors = []
        values = [(str(value).strip() if value is not None else '') for value in group.values()]
        if not any(values):
            return None, errors
        group_id = (group.get('group_id') or '').strip()
        if not group_id:
            errors.append('Пустой group_id у группы')
        elif ';' in group_id:
            errors.append(f'group_id содержит ";" ({group_id})')
        short_code = (group.get('short_code') or '').strip()
        if not short_code:
            errors.append(f'Пустой short_code у группы {group_id or "?"}')
        public_name = (group.get('public_name') or '').strip()
        if not public_name:
            errors.append(f'Пустой public_name у группы {group_id or "?"}')
        if errors:
            return None, errors
        normalized = {
            'group_id': group_id,
            'short_code': short_code,
            'broadcast_code': FromGoogleSpreadsheet._normalize_sheet_text(group.get('broadcast_code')),
            'tg_command': FromGoogleSpreadsheet._normalize_sheet_text(group.get('tg_command')),
            'public_name': FromGoogleSpreadsheet._normalize_sheet_text(group.get('public_name')),
            'conditions_url': FromGoogleSpreadsheet._normalize_sheet_text(group.get('conditions_url')),
            'tasks_header_template': FromGoogleSpreadsheet._normalize_sheet_text(group.get('tasks_header_template')),
            'switch_message': FromGoogleSpreadsheet._normalize_sheet_text(group.get('switch_message')),
            'sort_order': FromGoogleSpreadsheet._parse_int(group.get('sort_order'), 0, 'sort_order', errors),
            'is_active': FromGoogleSpreadsheet._parse_bool(group.get('is_active'), 1, 'is_active', errors),
            'is_default': FromGoogleSpreadsheet._parse_bool(group.get('is_default'), 0, 'is_default', errors),
            'allow_self_switch': FromGoogleSpreadsheet._parse_bool(group.get('allow_self_switch'), 0, 'allow_self_switch', errors),
            'is_system': FromGoogleSpreadsheet._parse_bool(group.get('is_system'), 0, 'is_system', errors),
            'score_weight': FromGoogleSpreadsheet._parse_float(group.get('score_weight'), 1.0, 'score_weight', errors),
        }
        return (normalized if not errors else None), errors

    @staticmethod
    def normalize_groups(groups: List[dict]):
        errors = []
        normalized = []
        seen_group_ids = set()
        seen_commands = set()
        seen_broadcasts = set()
        for group in groups:
            normalized_group, row_errors = FromGoogleSpreadsheet._normalize_group_row(group)
            if row_errors:
                errors += row_errors
                continue
            if not normalized_group:
                continue
            group_id = normalized_group['group_id']
            if group_id in seen_group_ids:
                errors.append(f'Дублирующийся group_id "{group_id}"')
                continue
            seen_group_ids.add(group_id)
            tg_command = normalized_group.get('tg_command')
            if tg_command:
                if tg_command in seen_commands:
                    errors.append(f'Дублирующаяся команда "{tg_command}"')
                    continue
                seen_commands.add(tg_command)
            broadcast_code = normalized_group.get('broadcast_code')
            if broadcast_code:
                if broadcast_code in seen_broadcasts:
                    errors.append(f'Дублирующийся broadcast_code "{broadcast_code}"')
                    continue
                seen_broadcasts.add(broadcast_code)
            normalized.append(normalized_group)
        return normalized, errors

    @staticmethod
    def groups_to_db(groups: List[dict]) -> List[str]:
        normalized_groups, errors = FromGoogleSpreadsheet.normalize_groups(groups)
        for group in normalized_groups:
            db.group.insert(group)
        return errors

    @staticmethod
    def students_to_db(students: List[dict]):
        for student in students:
            student['type'] = USER_TYPE.STUDENT
            student['middlename'] = ''
            student['chat_id'] = None
            student['birthday'] = student.get('birthday') or None
            student['grade'] = int(student['grade']) if student.get('grade') else None
            try:
                student['online'] = ONLINE_MODE_DECODER[student['online']]
            except:
                student['online'] = ONLINE_MODE.ONLINE
            student['allowed_groups'] = FromGoogleSpreadsheet._normalize_allowed_groups(student.get('allowed_groups'))
            student['group_id'] = FromGoogleSpreadsheet._pick_user_group_id(student.get('group_id'), student['allowed_groups'])
            user = User(**student)
            State.set_by_user_id(user.id, STATE.GET_TASK_INFO)


    @staticmethod
    def teachers_to_db(teachers: List[dict]):
        for teacher in teachers:
            teacher['type'] = USER_TYPE.TEACHER
            for non_teacher_key in ['chat_id', 'grade', 'birthday']:
                teacher[non_teacher_key] = None
            try:
                teacher['online'] = ONLINE_MODE_DECODER[teacher['online']]
            except:
                teacher['online'] = ONLINE_MODE.ONLINE
            teacher['allowed_groups'] = FromGoogleSpreadsheet._normalize_allowed_groups(teacher.get('allowed_groups'))
            teacher['group_id'] = FromGoogleSpreadsheet._pick_user_group_id(teacher.get('group_id'), teacher['allowed_groups'])
            User(**teacher)

    @staticmethod
    def ui_messages_to_db(ui_messages: List[dict]):
        for ui_message in ui_messages:
            key = ui_message['key']
            value = ui_message['value']
            if key and value:
                db.settings.add_ui_message(key, value)

    @staticmethod
    def bot_settings_to_db(bot_settings: List[dict]):
        for bot_setting in bot_settings:
            key = bot_setting['key']
            value = bot_setting['value']
            if key and value:
                db.settings.add_setting(key, value)

    @staticmethod
    def problems_to_db(problems: List[dict]) -> List[str]:
        errors = []
        for problem in problems:
            if problem['group_id'] == problem['lesson'] == problem['prob'] == problem['item'] == '':
                continue
            group_id = (problem.get('group_id') or '').strip()
            if not group_id:
                errors.append(f'Не указан group_id у задачи {problem!r}')
                continue
            if ';' in group_id:
                errors.append(f'group_id содержит ; у задачи {problem!r}')
                continue
            problem['group_id'] = group_id
            try:
                problem['prob_type'] = PROB_TYPES_DECODER[problem['prob_type']]
            except:
                errors.append(f'Кривой тип задачи у {problem!r}')
                continue
            try:
                if problem['prob_type'] == PROB_TYPE.TEST:
                    problem['ans_type'] = ANS_TYPES_DECODER[problem['ans_type']]
                else:
                    problem['ans_type'] = ''
            except:
                errors.append(f'Кривой тип ответа у тестовой задачи {problem!r}')
                continue
            try:
                if problem['ans_validation']:
                    re.compile(problem['ans_validation'])
            except:
                errors.append(f'Не компилируется регулярка валидации у задачи {problem!r}')
                continue
            Problem(**problem)
        # TODO Попахивает риском продолбать важное :(
        db.lesson.update()
        db.problem.update_synonyms(join=SYNONYMS_MODE == FEATURES.SYNONYMS_JOIN)
        return errors


def update_from_google_if_db_is_empty():
    # Если в базе нет ни одного учителя, то принудительно грузим всё из таблицы (иначе даже админ не сможет залогиниться)
    all_teachers = list(User.all_teachers())
    if len(all_teachers) == 0:
        FromGoogleSpreadsheet.update_all()
        all_teachers = list(User.all_teachers())
    logger.info(f'В базе в текущий момент {len(all_teachers)} учителей')


# db.sql.setup(config.db_filename)
# google_spreadsheet_loader.setup(config.google_sheets_key, config.google_cred_json)
#
# # Если в базе нет ни одного учителя, то принудительно грузим всё из таблицы
# all_teachers = list(User.all_teachers())
# if len(all_teachers) == 0:
#     FromGoogleSpreadsheet.update_all()
#     all_teachers = list(User.all_teachers())
# logger.info(f'В базе в текущий момент {len(all_teachers)} учителей')
