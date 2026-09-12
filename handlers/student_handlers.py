import datetime
import os
import io
import asyncio
from dataclasses import dataclass
from html import escape
from operator import itemgetter
from typing import Tuple, Optional
from types import SimpleNamespace

from aiogram import types
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from helpers.consts import *
from helpers.config import logger, config
import db_methods as db
from helpers.features import RESULT_MODE, FEATURES, SAVE_SOL_MODE, RATE_LIMIT_MODE
from helpers.msg_texts import msgs
from models import User, Problem, State, Waitlist, WrittenQueue, Result
from helpers.bot import bot, reg_callback, router, reg_state, group_router
from handlers import student_keyboards, common_keyboards
from helpers.game_scoring import apply_group_weight, build_group_weight_map
from helpers.pwa.test_checkers import (
    TRUSTED_CHECKER_GLOBALS,
    TRUSTED_CHECKER_PATTERN,
    TrustedCheckerExecutor,
    TrustedCheckerStatus,
)
from helpers.trace import emit_trace
from models.pwa.submissions import (
    SELECT_ONE_COMPATIBILITY_LIMIT,
    SubmissionConfigurationError,
    TestAnswerOutcome,
    TestProblemAnswerConfig,
    evaluate_test_answer,
)

SOLS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../solutions')
WHITEBOARD_LINK = "https://www.shashkovs.ru/jitboard.html?{}"
# Historical import aliases now point at the single Phase-4 checker policy.
GLOBALS_FOR_TEST_FUNCTION_CREATION = TRUSTED_CHECKER_GLOBALS
is_py_func = TRUSTED_CHECKER_PATTERN
MAX_CALLBACK_PAYLOAD_HOOK_LIMIT = SELECT_ONE_COMPATIBILITY_LIMIT
_TELEGRAM_TEST_CHECKER_EXECUTOR = TrustedCheckerExecutor()

_registered_group_commands = set()


def _normalize_group_command(raw_cmd: str) -> str:
    cmd = (raw_cmd or '').strip()
    if cmd.startswith('/'):
        cmd = cmd[1:]
    if '@' in cmd:
        cmd = cmd.split('@', 1)[0]
    return cmd.strip()


def _resolve_student_group_code(student: User) -> str:
    return student.group_code


def _render_group_header_text(header_template: str, *, student: User, mode_hint: str, group_ctx: SimpleNamespace) -> str:
    return header_template.format_map({'student': student, 'mode_hint': mode_hint, 'group': group_ctx}).replace('""', '"')


def register_group_switch_commands():
    groups = db.group.get_all()
    for group in groups:
        cmd = _normalize_group_command(group.get('tg_command') or '')
        if not cmd or cmd in _registered_group_commands:
            continue
        _registered_group_commands.add(cmd)
        group_router.message(Command(cmd))(switch_group_by_command)


async def _ensure_student_group_access(student: User, group_id: str, chat_id: int) -> bool:
    if not group_id or not student.can_access_group(group_id):
        await bot.send_message(chat_id=chat_id, text=msgs.no_access_to_group)
        return False
    return True


async def post_problem_keyboard(
    chat_id: int, student: User, *, blocked=False, show_lesson=None, disable_notification=False
):
    if student.type == USER_TYPE.UNKNOWN:
        State.set_by_user_id(student.id, STATE.GET_USER_INFO)
        await bot.send_message(
            chat_id=chat_id,
            text=msgs.auth_needed,
        )
        return

    prev_keyboard = db.last_keyboard.get(student.id)
    if prev_keyboard:
        try:
            await bot.edit_message_reply_markup_ig(
                chat_id=prev_keyboard['chat_id'], message_id=prev_keyboard['tg_msg_id'], reply_markup=None
            )
        except:
            pass

    group_id = student.group_id
    if student.type == USER_TYPE.STUDENT and not student.can_access_group(group_id):
        await bot.send_message(chat_id=chat_id, text=msgs.no_access_to_group)
        return
    # Теперь здесь странное. Если студенту назначен опрос, то показываем его
    survey = db.survey.get_active_survey(student.id)
    if survey:
        survey_result = db.survey.get_survey_result(student.id, survey['id'])
        keyb_msg = await bot.send_message(
            chat_id=chat_id,
            text=survey['question'],
            parse_mode='HTML',
            disable_web_page_preview=True,
            disable_notification=True,
            reply_markup=common_keyboards.build_survey(student, survey, survey_result),
        )
        db.last_keyboard.update(student.id, keyb_msg.chat.id, keyb_msg.message_id)
        return
    if not blocked:
        if student.online == ONLINE_MODE.ONLINE:
            mode_hint = msgs.online_mode_hint
        elif student.online == ONLINE_MODE.SCHOOL:
            mode_hint = msgs.offline_mode_hint
        else:
            mode_hint = '?'
        group = student.group
        if group:
            group_payload = dict(group.__dict__)
            if not group_payload.get('conditions_url'):
                group_payload['conditions_url'] = ''
            if not group_payload.get('public_name'):
                group_payload['public_name'] = ''
            group_ctx = SimpleNamespace(**group_payload)
            header_template = group.tasks_header_template or msgs.problems_keyboard_header
            has_custom_header_template = bool(group.tasks_header_template)
        else:
            group_code = _resolve_student_group_code(student)
            group_ctx = SimpleNamespace(
                public_name=group_code,
                conditions_url='',
            )
            header_template = msgs.problems_keyboard_header
            has_custom_header_template = False
        text = _render_group_header_text(header_template, student=student, mode_hint=mode_hint, group_ctx=group_ctx)
    else:
        text = msgs.solutions_are_not_accepted_now
    if show_lesson is None:
        show_lesson = Problem.last_lesson_num(group_id)
    try:
        keyb_msg = await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode='HTML',
            disable_web_page_preview=True,
            reply_markup=student_keyboards.build_problems(show_lesson, student),
            disable_notification=disable_notification,
        )
    except TelegramBadRequest as e:
        if blocked or not has_custom_header_template or 'parse entities' not in str(e).lower():
            raise
        logger.warning('Invalid group tasks_header_template for %s, fallback to default header: %s', group_id, e)
        fallback_text = _render_group_header_text(
            msgs.problems_keyboard_header,
            student=student,
            mode_hint=mode_hint,
            group_ctx=group_ctx,
        )
        keyb_msg = await bot.send_message(
            chat_id=chat_id,
            text=fallback_text,
            parse_mode='HTML',
            disable_web_page_preview=True,
            reply_markup=student_keyboards.build_problems(show_lesson, student),
            disable_notification=disable_notification,
        )
    except TelegramForbiddenError:
        # Дальше писать смысла нет
        student.set_chat_id(None)
        return
    db.last_keyboard.update(student.id, keyb_msg.chat.id, keyb_msg.message_id)


async def refresh_last_student_keyboard(student: User, force=False) -> bool:
    if not student:
        return False
    prev_keyboard = db.last_keyboard.get(student.id)
    if prev_keyboard:
        try:
            updated = await bot.edit_message_reply_markup(
                chat_id=prev_keyboard['chat_id'],
                message_id=prev_keyboard['tg_msg_id'],
                reply_markup=student_keyboards.build_problems(
                    Problem.last_lesson_num(student.group_id), student
                )
            )
            return bool(updated)
        except TelegramBadRequest as e:
            err = e.message.lower()
            if "message is not modified" in err:
                return True
            if "message to edit not found" in err:
                prev_keyboard = None
            else:
                return False
        except Exception as e:
            return False
    if not prev_keyboard and force and student.chat_id:
        await post_problem_keyboard(student.chat_id, student, disable_notification=True)
        return True
    return False


async def sleep_and_send_problems_keyboard(chat_id: int, student: User, sleep=1):
    if sleep > 0:
        await asyncio.sleep(sleep)
    await post_problem_keyboard(chat_id, student)


@reg_state(STATE.GET_TASK_INFO)
async def prc_get_task_info_state(message, student: User):
    logger.debug('prc_get_task_info_state')
    # Возможно, тут прилетел хвост галереи, которую мы успешно уже обработали.
    if message.media_group_id and db.media_group.check(message.media_group_id):
        await prc_sending_solution_state(message, student)
        return
    # Обрабатываем как обычно
    alarm = ''
    # Попытка сдать решение без выбранной задачи
    if message.photo or message.document:
        alarm = msgs.error_file_is_not_accepted
    elif message.text and len(message.text) > 20:
        alarm = msgs.error_text_is_not_accepted_now
    sleep = 0
    if alarm:
        await bot.send_message(chat_id=message.chat.id, text=alarm, )
        sleep = 8
    asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, student, sleep=sleep))


@reg_state(STATE.SENDING_SOLUTION)
async def prc_sending_solution_state(message: types.Message, student: User):
    logger.debug('prc_sending_solution_state')
    # Особый случай — это медиа-группы. Если несколько картинок  в одном сообщении,
    # то к нам в бот они придут в виде нескольких сообщений с одинаковым media_group_id.
    # Поэтому если media_group_id задан, то для первого сообщения нужно сохранить, к какой он задаче,
    # а потом уже брать id задачи из сохранённого
    next_media_group_message = False
    if message.media_group_id:
        problem_id = db.media_group.check(message.media_group_id)
        if problem_id:
            next_media_group_message = True
        else:
            problem_id = State.get_by_user_id(student.id)['problem_id']
            duplicate = db.media_group.insert(message.media_group_id, problem_id)
            # Могло так случиться, что в другом потоке в параллель добавили
            if duplicate:
                problem_id = db.media_group.check(message.media_group_id)
                next_media_group_message = True
    else:
        problem_id = State.get_by_user_id(student.id)['problem_id']
    emit_trace(
        "student.written_solution.submitted",
        user_id=student.id,
        target_user_id=student.id,
        chat_id=message.chat.id,
        problem_id=problem_id,
        is_sos=problem_id < 0,
        has_text=bool(message.text),
        text_len=len(message.text or ""),
        photo_count=len(message.photo or []),
        has_document=bool(message.document),
        doc_mime=(message.document and message.document.mime_type),
        doc_size=(message.document and message.document.file_size),
        media_group_id=message.media_group_id,
        next_media_group_message=next_media_group_message,
    )
    file_name = None
    text = message.text

    if SAVE_SOL_MODE == FEATURES.SAVE_SOL_ON_DRIVE:
        try:
            downloaded = []
            if text:
                downloaded.append((io.BytesIO(text.encode('utf-8')), 'text.txt'))
            # for photo in message.photo:
            if message.photo:
                file_info = await bot.get_file(message.photo[-1].file_id)
                downloaded_file = await bot.download_file(file_info.file_path)
                filename = file_info.file_path
                downloaded.append((downloaded_file, filename))
            if message.document:
                if message.document.file_size > 5 * 1024 * 1024:
                    await bot.send_message(
                        chat_id=message.chat.id,
                        text=msgs.error_file_is_too_large
                    )
                    return
                file_id = message.document.file_id
                file_info = await bot.get_file(file_id)
                downloaded_file = await bot.download_file(file_info.file_path)
                filename = file_info.file_path
                downloaded.append((downloaded_file, filename))
            problem = Problem.get_by_id(problem_id)
            for bin_data, filename in downloaded:
                ext = filename[filename.rfind('.') + 1:]
                cur_ts = datetime.datetime.now().isoformat().replace(':', '-')
                file_name = os.path.join(
                    SOLS_PATH,
                    f'{student.token} {student.surname} {student.name}',
                    f'{problem.lesson}',
                    f'{problem.lesson}{problem.group_code}_{problem.prob}{problem.item}_{cur_ts}.{ext}'
                )
                os.makedirs(os.path.dirname(file_name), exist_ok=True)
                db.log.insert(False, message.message_id, message.chat.id, student.id, None, message.text, file_name)
                with open(file_name, 'wb') as file:
                    file.write(bin_data.read())
        except Exception as e:
            logger.exception(e)
    WrittenQueue.add_to_discussions(student.id, problem_id, None, text, file_name, message.chat.id, message.message_id)
    if not next_media_group_message:
        WrittenQueue.add_to_queue(student.id, problem_id)
        await bot.send_message(
            chat_id=message.chat.id,
            text=msgs.sol_accepted if (problem_id > 0) else msgs.question_accepted
        )
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, student))


def check_test_ans_rate_limit(student_id: int, problem_id: int):
    logger.debug('check_test_ans_rate_limit')
    per_day, per_hour = db.result.check_num_answers(student_id, problem_id)
    text_to_student = None
    if per_hour >= 3:
        text_to_student = msgs.hour_rate_limit_error
    elif per_day >= 6:
        text_to_student = msgs.dayly_rate_limit_error
    return text_to_student


@unique
class ANS_CHECK_VERDICT(IntEnum):
    INCORRECT_SELECT = -2
    VALIDATION_NOT_PASSED = -3
    RATE_LIMIT = -4
    PENDING_CONFIGURATION = -5
    CORRECT = 1
    WRONG = -1


@dataclass(frozen=True, slots=True)
class TelegramTestAnswerDecision:
    verdict: ANS_CHECK_VERDICT
    display_answer: str
    counts_as_attempt: bool
    feedback: str
    checker_message: Optional[str] = None
    diagnostic_message: Optional[str] = None


def _legacy_problem_answer_config(problem: Problem) -> TestProblemAnswerConfig:
    return TestProblemAnswerConfig.from_revision(
        answer_type=int(problem.ans_type),
        answer_config={
            "answerValidation": problem.ans_validation,
            "validationError": problem.validation_error,
            "correctAnswer": problem.cor_ans,
            "correctAnswerChecker": problem.cor_ans_checker,
            "wrongAnswer": problem.wrong_ans,
            "congratulation": problem.congrat,
        },
    )


def evaluate_telegram_test_problem_answer(
    problem: Problem, student_answer: str | None
) -> TelegramTestAnswerDecision:
    """Evaluate Telegram input through the same policy as the Student PWA."""
    display_answer = "" if student_answer is None else student_answer.strip()
    try:
        evaluation = evaluate_test_answer(
            _legacy_problem_answer_config(problem),
            display_answer,
            trusted_executor=_TELEGRAM_TEST_CHECKER_EXECUTOR,
        )
    except (SubmissionConfigurationError, TypeError, ValueError):
        return TelegramTestAnswerDecision(
            verdict=ANS_CHECK_VERDICT.PENDING_CONFIGURATION,
            display_answer=display_answer,
            counts_as_attempt=True,
            feedback="Ответ принят и ожидает настройки проверки.",
            diagnostic_message=(
                "TEST_CHECKER_CONFIGURATION_ERROR: "
                f"problem_id={problem.id}; diagnostic=legacy_metadata_invalid"
            ),
        )

    diagnostic_message = None
    if evaluation.diagnostic_code:
        diagnostic_message = (
            "TEST_CHECKER_CONFIGURATION_ERROR: "
            f"problem_id={problem.id}; diagnostic={evaluation.diagnostic_code}"
        )
    if evaluation.outcome is TestAnswerOutcome.CORRECT:
        verdict = ANS_CHECK_VERDICT.CORRECT
    elif evaluation.outcome is TestAnswerOutcome.WRONG:
        verdict = ANS_CHECK_VERDICT.WRONG
    elif evaluation.outcome is TestAnswerOutcome.INVALID_FORMAT:
        verdict = (
            ANS_CHECK_VERDICT.INCORRECT_SELECT
            if problem.ans_type == ANS_TYPE.SELECT_ONE
            else ANS_CHECK_VERDICT.VALIDATION_NOT_PASSED
        )
    else:
        verdict = ANS_CHECK_VERDICT.PENDING_CONFIGURATION
    return TelegramTestAnswerDecision(
        verdict=verdict,
        display_answer=evaluation.display_answer,
        counts_as_attempt=evaluation.counts_as_attempt,
        feedback=evaluation.feedback or "Ответ принят и ожидает настройки проверки.",
        checker_message=evaluation.checker_message,
        diagnostic_message=diagnostic_message,
    )


def _telegram_test_rate_limit(
    problem: Problem, student: Optional[User], decision: TelegramTestAnswerDecision
) -> Optional[str]:
    if (
        RATE_LIMIT_MODE != FEATURES.RATE_LIMIT_3_AND_6
        or student is None
        or student.type != USER_TYPE.STUDENT
        or not decision.counts_as_attempt
    ):
        return None
    return check_test_ans_rate_limit(student.id, problem.id)


def run_py_func_checker(
    problem: Problem, student_answer: str, *, check_functions_cache=None
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Historical callable wrapper over the shared trusted-checker executor."""
    del check_functions_cache
    execution = _TELEGRAM_TEST_CHECKER_EXECUTOR.execute(
        problem.cor_ans_checker, student_answer.strip()
    )
    if execution.status is TrustedCheckerStatus.CHECKED:
        return bool(execution.correct), execution.message, None
    return (
        False,
        None,
        "TEST_CHECKER_CONFIGURATION_ERROR: "
        f"problem_id={problem.id}; diagnostic={execution.diagnostic_code}",
    )


def check_test_problem_answer(
    problem: Problem,
    student: Optional[User],
    student_answer: str,
    *,
    check_functions_cache=None,
) -> Tuple[
    ANS_CHECK_VERDICT, Optional[str], Optional[str]]:
    del check_functions_cache
    logger.debug('check_test_problem_answer')
    decision = evaluate_telegram_test_problem_answer(problem, student_answer)
    rate_limit_message = _telegram_test_rate_limit(problem, student, decision)
    if rate_limit_message:
        return ANS_CHECK_VERDICT.RATE_LIMIT, rate_limit_message, None
    student_message = decision.checker_message
    if decision.verdict is ANS_CHECK_VERDICT.PENDING_CONFIGURATION:
        student_message = decision.feedback
    return decision.verdict, student_message, decision.diagnostic_message


async def check_answer_and_react(chat_id: int, problem: Problem, student: User, student_answer: str):
    emit_trace(
        "student.test_answer.submitted",
        user_id=student.id,
        target_user_id=student.id,
        chat_id=chat_id,
        problem_id=problem and problem.id,
        lesson=problem and problem.lesson,
        group_id=problem and problem.group_id,
        answer_len=len(student_answer or ""),
        has_answer=bool(student_answer),
    )
    decision = evaluate_telegram_test_problem_answer(problem, student_answer)
    rate_limit_message = _telegram_test_rate_limit(problem, student, decision)
    if decision.diagnostic_message:
        await bot.post_logging_message(decision.diagnostic_message)
    if rate_limit_message:
        await bot.send_message(chat_id=chat_id, text=rate_limit_message)
        logger.info(f'Ограничили студента: {student.id}')
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        asyncio.create_task(sleep_and_send_problems_keyboard(chat_id, student))
        return
    if decision.checker_message:
        await bot.send_message(chat_id=chat_id, text=decision.checker_message)
    if decision.verdict == ANS_CHECK_VERDICT.INCORRECT_SELECT:
        variants = ', '.join(problem.ans_validation.split(';'))
        await bot.send_message(
            chat_id=chat_id, text=msgs.error_select_one_of.format_map({'variants': variants})
        )
    elif decision.verdict == ANS_CHECK_VERDICT.VALIDATION_NOT_PASSED:
        await bot.send_message(chat_id=chat_id, text=f"❌ {decision.feedback}")
    elif decision.verdict == ANS_CHECK_VERDICT.PENDING_CONFIGURATION:
        await bot.send_message(chat_id=chat_id, text=decision.feedback)
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        asyncio.create_task(sleep_and_send_problems_keyboard(chat_id, student))
    else:
        if decision.verdict == ANS_CHECK_VERDICT.CORRECT:
            Result.add(student, problem, None, VERDICT.SOLVED, decision.display_answer, RES_TYPE.TEST)
            text_to_student = f"✔️ {decision.feedback}"
        else:
            Result.add(student, problem, None, VERDICT.WRONG_ANSWER, decision.display_answer, RES_TYPE.TEST)
            text_to_student = f"❌ {decision.feedback}"
        if RESULT_MODE == FEATURES.RESULT_AFTER:
            text_to_student = msgs.results_after_answer_accepted
        await bot.send_message(chat_id=chat_id, text=text_to_student)
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        asyncio.create_task(sleep_and_send_problems_keyboard(chat_id, student))


@reg_state(STATE.SENDING_TEST_ANSWER)
async def prc_sending_test_answer_state(message: types.Message, student: User, check_functions_cache={}):
    logger.debug('prc_sending_test_answer_state')
    state = State.get_by_user_id(student.id)
    problem_id = state['problem_id']
    problem = Problem.get_by_id(problem_id)
    student_answer = (message.text or '').strip()
    await check_answer_and_react(message.chat.id, problem, student, student_answer)


@reg_state(STATE.WAIT_SOS_REQUEST)
async def prc_wait_sos_request_state(message: types.Message, student: User):
    logger.debug('prc_wait_sos_request_state')
    state = State.get_by_user_id(student.id)
    emit_trace(
        "student.sos.submitted",
        user_id=student.id,
        target_user_id=student.id,
        chat_id=message.chat.id,
        problem_id=state and state.get('problem_id'),
        has_text=bool(message.text),
        text_len=len(message.text or ""),
        has_photo=bool(message.photo),
        has_document=bool(message.document),
    )
    try:
        group_code = _resolve_student_group_code(student)
        text = (f'❓❓❓❓\n'
                f'<code>{student.surname}</code> <code>{student.name}</code>\n'
                f'<code>{group_code}</code> <code>{student.token}</code> {ONLINE_MODE(student.online).__str__()[12:]}\n'
                f'Команда для правки плюсов: <code>/edtplus_{Problem.last_lesson_num(student.group_id)}_{student.token}</code>')
        hdr_msg = await bot.send_message(config.sos_channel, parse_mode="HTML", text=text)
        que_msg = await bot.forward_message(config.sos_channel, message.chat.id, message.message_id)
        db.question.add(
            student.id, message.chat.id, message.message_id, message.text,
            hdr_msg.chat.id, hdr_msg.message_id,
            que_msg.message_id
        )
    except:
        logger.info(f'Не удалось переслать SOS-сообщение в канал {config.sos_channel}')
    await bot.send_message(chat_id=message.chat.id, text=msgs.question_accepted)
    if student.type == USER_TYPE.UNKNOWN:
        State.set_by_user_id(student.id, STATE.GET_USER_INFO)
    else:
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, student))


@reg_state(STATE.STUDENT_IS_SLEEPING)
async def prc_student_is_sleeping_state(message: types.message, student: User):
    logger.debug('prc_student_is_sleeping_state')
    await bot.send_message(
        chat_id=message.chat.id if message else student.chat_id,
        text=msgs.student_is_sleeping_state_msg
    )


@reg_state(STATE.STUDENT_IS_IN_CONFERENCE)
async def prc_student_is_in_conference_state(message: types.message, student: User):
    logger.debug('prc_student_is_in_conference_state')
    # Ничего не делаем, ждём callback'а
    pass


async def switch_group_by_command(message: types.Message):
    logger.debug('switch_group_by_command')
    if not message.text:
        return
    cmd = message.text.split()[0]
    if not cmd.startswith('/'):
        return
    if '@' in cmd:
        cmd = cmd.split('@', 1)[0]
    group = db.group.get_by_command(cmd)
    if not group and cmd.startswith('/'):
        group = db.group.get_by_command(cmd[1:])
    if not group:
        return
    user = User.get_by_chat_id(message.chat.id)
    if not user:
        return
    if not group.get('is_active'):
        await bot.send_message(chat_id=message.chat.id, text=msgs.no_access_to_group)
        return
    if user.type == USER_TYPE.STUDENT and not group.get('allow_self_switch'):
        await bot.send_message(chat_id=message.chat.id, text=msgs.no_access_to_group)
        return
    if not user.can_access_group(group['group_id']):
        await bot.send_message(chat_id=message.chat.id, text=msgs.no_access_to_group)
        return
    user.set_group_id(group['group_id'])
    switch_message = group.get('switch_message') or f'Вы переведены в группу «{group.get("public_name") or ""}».'
    message = await bot.send_message(
        chat_id=message.chat.id,
        text=switch_message,
    )
    if State.get_by_user_id(user.id)['state'] != STATE.STUDENT_IS_SLEEPING:
        State.set_by_user_id(user.id, STATE.GET_TASK_INFO)
    asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, user))


@router.message(Command('sos'))
async def sos(message: types.Message):
    logger.debug('sos')
    user = User.get_by_chat_id(message.chat.id)
    emit_trace(
        "student.sos.started",
        chat_id=message.chat.id,
        user_id=user and user.id,
        target_user_id=user and user.id,
        user_exists=bool(user),
    )
    if not user:
        token = f'unknown{message.chat.id}'
        if message.chat.username:
            token += f'@{message.chat.username}'
        new_unknown_user = User(
            chat_id=message.chat.id,
            type=USER_TYPE.UNKNOWN,
            name=message.chat.first_name or '',
            surname=message.chat.last_name or '',
            middlename='',
            token=token,
            online=ONLINE_MODE.ONLINE,
            grade=12,
            birthday=None,
        )
        db.log.log_signon(
            new_unknown_user and new_unknown_user.id, message.chat.id, message.chat.first_name, message.chat.last_name,
            message.chat.username,
            token
        )
        State.set_by_user_id(new_unknown_user.id, STATE.WAIT_SOS_REQUEST)
        await bot.send_message(
            chat_id=message.chat.id,
            text=msgs.error_sos_without_auth,
        )
    else:
        sos_message = await bot.send_message(
            chat_id=message.chat.id,
            text=msgs.sos_what_is_your_question,
            reply_markup=student_keyboards.build_student_sos_actions()
        )
        bot.delete_messages_after(sos_message, 30)


@reg_callback(CALLBACK.PROBLEM_SOS)
async def prc_problem_sos_callback(query: types.CallbackQuery, student: User):
    await bot.delete_message_ig(chat_id=query.message.chat.id, message_id=query.message.message_id)
    if not await _ensure_student_group_access(student, student.group_id, query.message.chat.id):
        await bot.answer_callback_query_ig(query.id)
        return
    problem_sos_message = await bot.send_message(
        chat_id=query.message.chat.id,
        text=msgs.sos_which_problem_question,
        reply_markup=student_keyboards.build_problems(
            Problem.last_lesson_num(student.group_id), student,
            is_sos_question=True
        )
    )
    bot.delete_messages_after(problem_sos_message, 30)
    await bot.answer_callback_query_ig(query.id)


@reg_callback(CALLBACK.OTHER_SOS)
async def prc_problems_other_sos_callback(query: types.CallbackQuery, student: User):
    await bot.delete_message_ig(chat_id=query.message.chat.id, message_id=query.message.message_id)
    State.set_by_user_id(student.id, STATE.WAIT_SOS_REQUEST)
    await bot.send_message(
        chat_id=query.message.chat.id,
        text=msgs.sos_other_question,
        reply_markup=student_keyboards.build_cancel_task_submission()
    )
    await bot.answer_callback_query_ig(query.id)


@reg_callback(CALLBACK.SOS_PROBLEM_SELECTED)
async def prc_problem_sos_problem_selected_callback(query: types.CallbackQuery, student: User):
    problem_id = int(query.data[2:])
    problem = Problem.get_by_id(problem_id)
    if not problem or not student.can_access_group(problem.group_id):
        await bot.answer_callback_query_ig(query.id)
        await bot.send_message(chat_id=query.message.chat.id, text=msgs.no_access_to_group)
        return
    State.set_by_user_id(student.id, STATE.WAIT_SOS_REQUEST, problem_id=problem_id)
    await bot.delete_message_ig(chat_id=query.message.chat.id, message_id=query.message.message_id)
    await bot.send_message(
        chat_id=query.message.chat.id,
        text=msgs.sos_problem_selected.format_map({'problem': problem}),
        reply_markup=student_keyboards.build_cancel_task_submission()
    )
    State.set_by_user_id(
        student.id, STATE.SENDING_SOLUTION,
        -problem_id
    )  # -problem_id - ВОПРОС по задаче, а не РЕШЕНИЕ
    await bot.answer_callback_query_ig(query.id)


@reg_callback(CALLBACK.PROBLEM_SELECTED)
async def prc_problems_selected_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_problems_selected_callback')
    state = State.get_by_user_id(student.id)
    if state and state['state'] == STATE.STUDENT_IS_SLEEPING:
        await bot.answer_callback_query_ig(query.id)
        return
    problem_id = int(query.data[2:])
    problem = Problem.get_by_id(problem_id)
    emit_trace(
        "student.problem.selected",
        user_id=student.id,
        target_user_id=student.id,
        chat_id=query.message.chat.id,
        problem_id=problem_id,
        lesson=problem and problem.lesson,
        group_id=problem and problem.group_id,
        prob_type=(int(problem.prob_type) if problem else None),
        ans_type=(int(problem.ans_type) if (problem and problem.ans_type) else None),
    )
    # Удаляем сообщение с клавиатурой-списком задач
    await bot.delete_message_ig(chat_id=query.message.chat.id, message_id=query.message.message_id)
    db.last_keyboard.delete(student.id)
    if not problem:
        await bot.answer_callback_query_ig(query.id)
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student))
        return
    if not student.can_access_group(problem.group_id):
        await bot.answer_callback_query_ig(query.id)
        await bot.send_message(chat_id=query.message.chat.id, text=msgs.no_access_to_group)
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student))
        return
    # В зависимости от типа задачи разное поведение
    elif problem.prob_type == PROB_TYPE.TEST:
        # Если это выбор из нескольких вариантов, то нужно сделать клавиатуру
        if problem.ans_type == ANS_TYPE.SELECT_ONE:
            await bot.send_message(
                chat_id=query.message.chat.id,
                text=msgs.answer_select_one_of.format_map({'problem': problem}),
                reply_markup=student_keyboards.build_test_answers(problem)
            )
        elif problem.ans_type == ANS_TYPE.WEEKDAY:
            # Мерзкий хардкод :(
            # TODO
            problem.ans_validation = 'Понедельник;Вторник;Среда;Четверг;Пятница;Суббота;Воскресенье'
            await bot.send_message(
                chat_id=query.message.chat.id,
                text=msgs.answer_select_day_of_week.format_map({'problem': problem}),
                reply_markup=student_keyboards.build_test_answers(problem)
            )
        else:
            answer_recommendation = problem.validation_error or msgs.answer_now_enter_answer.format_map({'problem': problem})
            await bot.send_message(
                chat_id=query.message.chat.id,
                text=msgs.answer_follow_recommendations.format_map({'problem': problem, 'answer_recommendation': answer_recommendation}),
                reply_markup=student_keyboards.build_cancel_task_submission()
            )
        State.set_by_user_id(student.id, STATE.SENDING_TEST_ANSWER, problem_id)
        await bot.answer_callback_query_ig(query.id)
    elif problem.prob_type in (PROB_TYPE.WRITTEN, PROB_TYPE.WRITTEN_BEFORE_ORALLY):
        await bot.send_message(
            chat_id=query.message.chat.id,
            text=msgs.answer_send_text_or_photo.format_map({'problem': problem}),
            reply_markup=student_keyboards.build_cancel_task_submission()
        )
        State.set_by_user_id(student.id, STATE.SENDING_SOLUTION, problem_id)
        await bot.answer_callback_query_ig(query.id)
    elif problem.prob_type == PROB_TYPE.ORALLY:
        text = msgs.zoom_instruction.format_map({'student': student})
        await bot.send_message(
            chat_id=query.message.chat.id,
            text=text,
            disable_web_page_preview=True,
            parse_mode='HTML'
        )
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        await bot.answer_callback_query_ig(query.id)
        asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student, sleep=5))

        # state = states.get_by_user_id(student.id)
        # if state['oral_problem_id'] is not None:
        #     await bot.send_message(chat_id=query.message.chat.id,
        #                            text="Вы уже стоите в очереди на устную сдачу\. " \
        #                                 "Дождитесь, когда освободится один из преподавателей\. " \
        #                                 "Тогда можно будет сдать сразу несколько задач\.",
        #                            parse_mode="MarkdownV2")
        #     await bot.answer_callback_query_ig(query.id)
        # else:
        #     try:
        #         await bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)
        #     except:
        #         pass
        #     waitlist.enter(student.id, problem.id)
        #     await bot.send_message(chat_id=query.message.chat.id,
        #                            text="Вы встали в очередь на устную сдачу\.\nЧтобы выйти из очереди, нажмите `/exit_waitlist`",
        #                            parse_mode="MarkdownV2",
        #                            reply_markup=student_keyboards.build_exit_waitlist())
        #     await bot.answer_callback_query_ig(query.id)
        #     asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student, sleep=4))


#         # await bot.send_message(chat_id=query.message.chat.id,
#         #                        text=f"Выбрана устная задача. "
#         #                             f"Её нужно сдавать в zoom-конференции. "
#         #                        # f"Желательно перед сдачей записать ответ и основные шаги решения на бумаге. "
#         #                        # f"Делайте рисунок очень крупным, чтобы можно было показать его преподавателю через видеокамеру. "
#         #                        # f"\nКогда у вас всё готово, "
#         #                             f"<b>Заходите в zoom-конференцию, идентификатор конференции:"
#         #                             f"\n83488340620, код доступа: 179179179</b>. "
#         #                             f"\nПожалуйста, при входе поставьте актуальную подпись: ваши фамилию и имя. "
#         #                             f"Как только один из преподавателей освободится, вас пустят в конференцию и переведут в комнату к преподавателю. "
#         #                             f"После окончания сдачи нужно выйти из конференции. "
#         #                             f"Когда у вас появится следующая устная задача, этот путь нужно будет повторить заново. "
#         #                             f"Мы постараемся выделить время каждому, но ожидание может быть достаточно долгим.",
#         #                        disable_web_page_preview=True,
#         #                        parse_mode='HTML')
#         # State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
#         # await bot.answer_callback_query_ig(query.id)
#         # asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student, sleep=5))
#
#         state = State.get_by_user_id(student.id)
#         if state['oral_problem_id'] is not None:
#             await bot.send_message(chat_id=query.message.chat.id,
#                                    text="Вы уже стоите в очереди на устную сдачу\. " \
#                                         "Дождитесь, когда освободится один из преподавателей\. " \
#                                         "Тогда можно будет сдать сразу несколько задач\.",
#                                    parse_mode="MarkdownV2")
#             await bot.answer_callback_query_ig(query.id)
#         else:
#             try:
#                 await bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)
#             except:
#                 pass
#             Waitlist.enter(student.id, problem.id)
#             await bot.send_message(chat_id=query.message.chat.id,
#                                    text="Вы встали в очередь на устную сдачу\.\nЧтобы выйти из очереди, нажмите `/exit_waitlist`",
#                                    parse_mode="MarkdownV2",
#                                    reply_markup=student_keyboards.build_exit_waitlist())
#             await bot.answer_callback_query_ig(query.id)
#             asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student, sleep=4))


@reg_callback(CALLBACK.LIST_SELECTED)
async def prc_list_selected_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_list_selected_callback')
    lesson = int(query.data[2:])
    student = User.get_by_chat_id(query.message.chat.id)
    if not await _ensure_student_group_access(student, student.group_id, query.message.chat.id):
        await bot.answer_callback_query_ig(query.id)
        return
    await post_problem_keyboard(student.chat_id, student, show_lesson=lesson)
    await bot.answer_callback_query_ig(query.id)


@reg_callback(CALLBACK.SHOW_LIST_OF_LISTS)
async def prc_show_list_of_lists_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_show_list_of_lists_callback')
    if not await _ensure_student_group_access(student, student.group_id, query.message.chat.id):
        await bot.answer_callback_query_ig(query.id)
        return
    await bot.edit_message_text_ig(
        chat_id=query.message.chat.id, message_id=query.message.message_id,
        text=msgs.list_of_all_topics,
        reply_markup=student_keyboards.build_lessons(group_id=student.group_id)
    )
    await bot.answer_callback_query_ig(query.id)


# TEMP_KVANTLANDIA
@reg_callback(CALLBACK.KVANTLANDIA)
async def prc_kvantlandia_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_kvantlandia_callback')
    kv_login = db.kv_login.get_by_user_id(student.id)
    if kv_login and kv_login.get('kv_login') and kv_login.get('kv_password'):
        text = (
            'Для участия в турнире откройте страницу https://math.kvantland.com/, '
            'нажмите кнопку "Открыть турнир ... класса" (по вашему выбору).\n'
            'Для входа используйте следующие данные:\n'
            f'логин: <code>{escape(kv_login["kv_login"])}</code>\n'
            f'пароль: <code>{escape(kv_login["kv_password"])}</code>\n'
            'Желаем успехов!'
        )
    else:
        text = (
            'Для участия в турнире откройте страницу https://math.kvantland.com/, '
            'нажмите кнопку "Открыть турнир ... класса" (по вашему выбору), '
            'нажмите кнопку "Регистрация" и заполните форму.\n'
            'Желаем успехов!'
        )
    await bot.send_message(chat_id=query.message.chat.id, text=text, parse_mode='HTML')
    await bot.answer_callback_query_ig(query.id)


@reg_callback(CALLBACK.ONE_OF_TEST_ANSWER_SELECTED)
async def prc_one_of_test_answer_selected_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_one_of_test_answer_selected_callback')
    problem = selected_answer = problem_id = None
    splitted = query.data.split('_', maxsplit=2)
    if len(splitted) == 3:
        _, problem_id, selected_answer = splitted
        problem = Problem.get_by_id(problem_id)

    await bot.edit_message_reply_markup_ig(
        chat_id=query.message.chat.id, message_id=query.message.message_id, reply_markup=None
    )
    await bot.answer_callback_query_ig(query.id)

    if problem is None:
        logger.error('Сломался приём задач :(')
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        # Удаляем варианты после изменения state'а. Иначе можно «зависнуть»
        asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student))
        return
    if not student.can_access_group(problem.group_id):
        await bot.send_message(chat_id=query.message.chat.id, text=msgs.no_access_to_group)
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student))
        return

    await bot.send_message(chat_id=query.message.chat.id, text=msgs.select_one_of_answer_selected.format_map({'selected_answer': selected_answer}))

    await check_answer_and_react(query.message.chat.id, problem, student, selected_answer)


@reg_callback(CALLBACK.CANCEL_TASK_SUBMISSION)
async def prc_cancel_task_submission_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_cancel_task_submission_callback')
    State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
    try:
        await bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)
    except:
        pass
    await bot.answer_callback_query_ig(query.id)
    asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student, sleep=0))


@reg_callback(CALLBACK.GET_OUT_OF_WAITLIST)
async def prc_get_out_of_waitlist_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_get_out_of_waitlist_callback')
    state = State.get_by_user_id(student.id)
    teacher = User.get_by_id(state['last_teacher_id'])
    await bot.edit_message_reply_markup_ig(
        chat_id=query.message.chat.id, message_id=query.message.message_id,
        reply_markup=None
    )
    Waitlist.leave(student.id)
    emit_trace(
        "student.waitlist.left",
        user_id=student.id,
        target_user_id=student.id,
        chat_id=query.message.chat.id,
        trigger="callback",
    )
    db.delete_url_by_user_id(student.id)
    try:
        await bot.unpin_chat_message(chat_id=query.message.chat.id)
    except TelegramBadRequest:
        pass
    State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
    if teacher:
        await bot.send_message(
            chat_id=teacher.chat_id,
            text=f"Ученик {student.surname} {student.name} {student.token} завершил устную сдачу.\n"
        )
    await bot.answer_callback_query_ig(query.id)
    asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student))


@router.message(Command('exit_waitlist'))
async def exit_waitlist(message: types.Message):
    logger.debug('exit_waitlist')
    user = User.get_by_chat_id(message.chat.id)
    Waitlist.leave(user.id)
    emit_trace(
        "student.waitlist.left",
        user_id=user and user.id,
        target_user_id=user and user.id,
        chat_id=message.chat.id,
        trigger="command",
    )
    db.delete_url_by_user_id(user.id)
    try:
        await bot.unpin_chat_message(chat_id=message.chat.id)
    except TelegramBadRequest:
        pass
    await bot.send_message(
        chat_id=message.chat.id,
        text=msgs.left_zoom_queue,
        reply_markup=types.ReplyKeyboardRemove()
    )
    asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, user))


# @router.message(Command('set_zoom'))
# async def set_zoom(message: types.Message):
#     logger.debug('set_zoom')
#     user = User.get_by_chat_id(message.chat.id)
#     zoom_conf = re.search(r'https://[\w?=._/-]*zoom[\w?=._/-]*', message.text or '')
#     if not zoom_conf:
#         await bot.send_message(
#             chat_id=message.chat.id,
#             text="Не смог найти в сообщении адрес конференции."
#         )
#         await bot.send_message(
#             chat_id=message.chat.id,
#             text="Открываете приложение zoom и стартуете новую конференцию.<br>В левом верхнем углу зелёный щит. Кликаете на него и копируете ссылку на вашу конференцию.<br>Запускаете вмш-телеграм-бота и пишете команду с вашей ссылкой вида <br><code>/set_zoom https://us02web.zoom.us/j/123?pwd=ABC</code>",
#             parse_mode="HTML"
#         )
#         asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, user, sleep=5))
#     else:
#         zoom_url = zoom_conf.group()
#         db.add_zoom_conf(user.id, zoom_url)
#         msg = await bot.send_message(
#             chat_id=message.chat.id,
#             text=f"Ожидайте вашей очереди и не выходите из конференции {zoom_url}.\nВыполните команду /exit_waitlist для отмены.", )
#         await bot.pin_chat_message(chat_id=message.chat.id, message_id=msg.message_id)
#         asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, user, sleep=5))


@router.message(Command('results'))
async def students_my_results(message: types.Message):
    logger.debug('students_my_results')
    student = User.get_by_chat_id(message.chat.id)
    emit_trace(
        "student.results.requested",
        user_id=student and student.id,
        target_user_id=student and student.id,
        chat_id=message.chat.id,
    )
    rows = db.result.list_all_student_results(student.id)
    if rows:
        lessons = {row['lesson'] for row in rows}
        for lesson in sorted(lessons):
            lines = [f'{row["ts"][5:16]} ' \
                     f'{row["lesson"]:02}{row["group_code"]}.{row["prob"]:02}{row["item"]:<1} ' \
                     f'{VERDICT_DECODER[row["verdict"]]} ' \
                     f'{row["answer"] if row["answer"] is not None else ""}'
                     for row in rows
                     if row['lesson'] == lesson
                     ]
            for i in range(0, len(lines), 20):
                try:
                    await bot.send_message(
                        chat_id=message.chat.id, parse_mode="HTML", text='<pre>' + '\n'.join(lines[i:i + 20]) + '</pre>'
                    )
                except TelegramBadRequest:
                    pass
    else:
        await bot.send_message(chat_id=message.chat.id, text=msgs.error_nothing_was_sent)


@router.message(Command('game_info'))
async def game_info(message: types.Message):
    """Отчёт по плюсам и минусам в игре.
    См. также get_game_data.
    """
    logger.debug('game_info')
    student = User.get_by_chat_id(message.chat.id)
    if student and student.type == USER_TYPE.TEACHER:
        try:
            cmd, token = message.text.split()
            student = User.get_by_token(token)
        except:
            pass
    if not student:
        return
    command = db.game.get_student_command(student.id)
    student_command = command['command_id'] if command else -1
    solved = db.result.get_student_solved(
        student.id,
        Problem.last_lesson_num(student.group_id),
    )  # ts, title, group_id, group_code
    payments = db.game.get_student_payments(student.id, student_command)  # ts, amount
    chests_rows = db.game.get_student_chests(student.id, student_command)
    # Собираем из решённых задач и оплат event'ы
    events = []
    for paym in payments:
        events.append([paym['ts'], '$', -paym['amount'], None])
    for chest in chests_rows:
        events.append([chest['ts'], '🗝', chest['bonus'], None])
    used_titles = set()
    weight_map = build_group_weight_map()
    command_group_code = command['group_code'] if command else None
    scores_count = {}
    for solv in solved:
        if '⚡' not in solv['title']:
            continue
        score, clear_title = solv['title'].split('⚡')
        score = int(score) if score.strip().isdecimal() else 2
        if clear_title in used_titles:
            continue
        else:
            used_titles.add(clear_title)
        score = apply_group_weight(score, solv['group_code'], command_group_code, weight_map=weight_map)
        events.append([solv['ts'], '+', score, clear_title.strip()])
    events.sort(key=itemgetter(0))
    report = []
    tp = None
    for ts, tp, diff, title in events:
        if tp == '$':
            report.append(f'{diff:+}⚡')
            for try_amount in range(-diff, 11):
                if scores_count.get(try_amount, 0) <= 0:
                    continue
                scores_count[try_amount] -= 1
                rem = try_amount + diff
                if rem > 0:
                    scores_count[rem] = scores_count.get(rem, 0) + 1
                break
        elif tp == '🗝':
            report.append(msgs.game_for_chest.format_map({'diff': diff}))
            scores_count[diff] = scores_count.get(diff, 0) + 1
        elif tp == '+':
            report.append(msgs.game_for_problem.format_map({'diff': diff, 'title': title}))
            scores_count[diff] = scores_count.get(diff, 0) + 1
        if tp != '$':
            report.append('    ' + ', '.join(f'{dif}⚡×{cnt}' for (dif, cnt) in sorted(scores_count.items()) if cnt > 0))
    if tp == '$':
        report.append('    ' + ', '.join(f'{dif}⚡×{cnt}' for (dif, cnt) in sorted(scores_count.items()) if cnt > 0))
    report = '\n'.join(report)
    for i in range(0, len(report), 4000):
        await bot.send_message(chat_id=message.chat.id, parse_mode="HTML", text=f'<pre>{report[i:i + 4000]}</pre>')
        await asyncio.sleep(1 / 20)
