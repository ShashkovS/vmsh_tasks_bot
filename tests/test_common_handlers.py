from __future__ import annotations

import pytest

import db_methods as db
from handlers import common_handlers
from helpers.consts import REACTION, RES_TYPE, SURVEY_TYPES, VERDICT
from helpers.msg_texts import msgs
from models import Problem, Result

from .telegram_harness import make_callback_query, make_message

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    ("reaction_type", "message_text", "result_field", "zoom_field", "expected_prefix"),
    [
        (REACTION.WRITTEN_TEACHER, "Teacher header\nfull discussion", "result_id", None, "Teacher header"),
        (REACTION.ORAL_TEACHER, "Oral teacher feedback", None, "zoom_conversation_id", "Oral teacher feedback"),
        (REACTION.WRITTEN_STUDENT, "TaskHeader more text", "result_id", None, "TaskHeader"),
        (REACTION.ORAL_STUDENT, "Oral student feedback", None, "zoom_conversation_id", "Oral student feedback"),
    ],
)
async def test_reaction_callback_saves_reaction_and_edits_message(
    scenario_env, reaction_type, message_text, result_field, zoom_field, expected_prefix
):
    data = scenario_env["data"]
    student = data.bind_chat(data.get_user("qwerty1"), 81001)
    teacher = data.bind_chat(data.get_teacher(), 81002)
    problem = Problem.get_by_key("i27c", 1, 1, "")
    assert problem is not None
    reaction_enum = db.reaction.enum(reaction_type)
    assert reaction_enum
    reaction_id = reaction_enum[0]["reaction_id"]
    reaction_text = reaction_enum[0]["reaction"]

    result_id = None
    zoom_conversation_id = None
    if result_field:
        result_id = Result.add(student, problem, teacher, VERDICT.SOLVED, None, RES_TYPE.WRITTEN)
    if zoom_field:
        zoom_conversation_id = db.zoom_conversation.insert(
            student_id=student.id,
            teacher_id=teacher.id,
            lesson=problem.lesson,
            group_id=problem.group_id,
        )

    query = make_callback_query(
        f"r_{result_id if result_id is not None else 'None'}_{zoom_conversation_id if zoom_conversation_id is not None else 'None'}_{reaction_id}_{int(reaction_type)}",
        chat_id=student.chat_id,
        message_id=1,
    )
    query.message.text = message_text

    await common_handlers.prc_reaction(query, student)

    reaction_row = db.sql.conn.execute("select * from reactions order by id desc limit 1").fetchone()
    assert reaction_row is not None
    assert reaction_row["reaction_id"] == reaction_id
    assert reaction_row["reaction_type_id"] == int(reaction_type)
    assert reaction_row["result_id"] == result_id
    assert reaction_row["zoom_conversation_id"] == zoom_conversation_id
    assert query.message.edit_text_calls
    assert query.message.edit_text_calls[-1]["text"] == f"{expected_prefix}\n\n{reaction_text}"
    assert query.answer_calls[-1]["text"] == msgs.reaction_accepted


async def test_survey_callback_updates_radio_and_checkbox_results(scenario_env):
    data = scenario_env["data"]
    user = data.bind_chat(data.get_user("qwerty1"), 82001)
    survey_id = db.survey.add_survey(SURVEY_TYPES.RADIO, True, "Choose one", ["One", "Two"])
    radio_survey = db.survey.get_survey_by_id(survey_id)
    first_choice_id = radio_survey["choices"][0]["id"]
    second_choice_id = radio_survey["choices"][1]["id"]

    radio_query = make_callback_query(
        f"S_{user.id}_{survey_id}_{SURVEY_TYPES.RADIO.value}_{first_choice_id}_",
        chat_id=user.chat_id,
        message_id=11,
    )
    await common_handlers.prc_survey(radio_query, user)
    assert db.survey.get_survey_result(user.id, survey_id) == [first_choice_id]
    assert scenario_env["bot"].edited_reply_markups
    assert scenario_env["bot"].answered_callbacks[-1]["id"] == radio_query.id

    checkbox_id = db.survey.add_survey(SURVEY_TYPES.CHECKBOX, True, "Choose many", ["A", "B"])
    checkbox_survey = db.survey.get_survey_by_id(checkbox_id)
    choice_a = checkbox_survey["choices"][0]["id"]
    choice_b = checkbox_survey["choices"][1]["id"]
    db.survey.update_survey_result(user.id, checkbox_id, [choice_a, choice_b])

    checkbox_query = make_callback_query(
        f"S_{user.id}_{checkbox_id}_{SURVEY_TYPES.CHECKBOX.value}_{choice_b}_{choice_a};{choice_b}",
        chat_id=user.chat_id,
        message_id=12,
    )
    await common_handlers.prc_survey(checkbox_query, user)
    assert db.survey.get_survey_result(user.id, checkbox_id) == [choice_a]


async def test_password_command_sends_password_for_known_user_and_ignores_unknown_chat(scenario_env):
    data = scenario_env["data"]
    user = data.bind_chat(data.get_user("qwerty1"), 83001)
    bot = scenario_env["bot"]

    await common_handlers.get_my_password(make_message(user.chat_id, text="/password", message_id=1))
    assert any(msg.chat.id == user.chat_id and user.token in (msg.text or "") for msg in bot.sent_messages)

    before = len(bot.sent_messages)
    await common_handlers.get_my_password(make_message(999999, text="/password", message_id=2))
    assert len(bot.sent_messages) == before
