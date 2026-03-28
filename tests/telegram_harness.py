from __future__ import annotations

import asyncio
from io import BytesIO
from types import SimpleNamespace


class RecordingMessage(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.edit_text_calls = []
        self.answer_calls = []

    async def edit_text(self, text, **kwargs):
        self.edit_text_calls.append({"text": text, "kwargs": kwargs})
        self.text = text
        return True

    async def answer(self, text=None, **kwargs):
        self.answer_calls.append({"text": text, "kwargs": kwargs})
        return True


class RecordingCallbackQuery(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.answer_calls = []

    async def answer(self, text=None, **kwargs):
        self.answer_calls.append({"text": text, "kwargs": kwargs})
        return True


def make_chat(chat_id: int, *, first_name: str = "Test", last_name: str = "User", username: str = "testuser"):
    return SimpleNamespace(
        id=chat_id,
        type="private",
        first_name=first_name,
        last_name=last_name,
        username=username,
    )


def make_message(
    chat_id: int,
    *,
    text: str | None = None,
    message_id: int = 1,
    photo=None,
    document=None,
    media_group_id=None,
    reply_to_message=None,
    first_name: str = "Test",
    last_name: str = "User",
    username: str = "testuser",
):
    chat = make_chat(chat_id, first_name=first_name, last_name=last_name, username=username)
    return RecordingMessage(
        message_id=message_id,
        chat=chat,
        text=text,
        photo=photo or [],
        document=document,
        media_group_id=media_group_id,
        reply_to_message=reply_to_message,
        from_user=SimpleNamespace(
            id=chat_id,
            is_bot=False,
            first_name=first_name,
            last_name=last_name,
            username=username,
        ),
    )


def make_callback_query(
    data: str,
    *,
    chat_id: int,
    message_id: int = 1,
    query_id: str = "cbq-1",
    first_name: str = "Test",
    last_name: str = "User",
    username: str = "testuser",
):
    return RecordingCallbackQuery(
        id=query_id,
        data=data,
        message=make_message(
            chat_id,
            message_id=message_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
        ),
    )


class RecordingBot:
    def __init__(self):
        self.username = "vmsh_test_bot"
        self._message_id = 1000
        self.sent_messages = []
        self.edited_texts = []
        self.edited_reply_markups = []
        self.deleted_messages = []
        self.answered_callbacks = []
        self.forwarded_messages = []
        self.copied_messages = []
        self.sent_photos = []
        self.sent_documents = []
        self.posted_logs = []
        self.unpinned_chats = []
        self.set_commands_calls = []

    def _next_message_id(self) -> int:
        self._message_id += 1
        return self._message_id

    async def send_message(self, chat_id, text, **kwargs):
        message = SimpleNamespace(
            chat=SimpleNamespace(id=chat_id),
            message_id=self._next_message_id(),
            text=text,
            kwargs=kwargs,
        )
        self.sent_messages.append(message)
        return message

    async def edit_message_text_ig(self, *, chat_id, message_id, text, **kwargs):
        self.edited_texts.append(
            {"chat_id": chat_id, "message_id": message_id, "text": text, "kwargs": kwargs}
        )
        return True

    async def edit_message_reply_markup_ig(self, *, chat_id, message_id, reply_markup=None, **kwargs):
        self.edited_reply_markups.append(
            {"chat_id": chat_id, "message_id": message_id, "reply_markup": reply_markup, "kwargs": kwargs}
        )
        return True

    async def edit_message_reply_markup(self, *, chat_id, message_id, reply_markup=None, **kwargs):
        self.edited_reply_markups.append(
            {"chat_id": chat_id, "message_id": message_id, "reply_markup": reply_markup, "kwargs": kwargs}
        )
        return True

    async def answer_callback_query_ig(self, callback_query_id, **kwargs):
        self.answered_callbacks.append({"id": callback_query_id, "kwargs": kwargs})
        return True

    async def delete_message_ig(self, *, chat_id, message_id, **kwargs):
        self.deleted_messages.append({"chat_id": chat_id, "message_id": message_id, "kwargs": kwargs})
        return True

    async def delete_message(self, chat_id, message_id, **kwargs):
        self.deleted_messages.append({"chat_id": chat_id, "message_id": message_id, "kwargs": kwargs})
        return True

    async def forward_message(self, chat_id, from_chat_id, message_id, **kwargs):
        message = SimpleNamespace(
            chat=SimpleNamespace(id=chat_id),
            message_id=self._next_message_id(),
            from_chat_id=from_chat_id,
            forwarded_message_id=message_id,
            kwargs=kwargs,
        )
        self.forwarded_messages.append(message)
        return message

    async def copy_message(self, chat_id, from_chat_id, message_id, **kwargs):
        payload = {
            "chat_id": chat_id,
            "from_chat_id": from_chat_id,
            "message_id": message_id,
            "kwargs": kwargs,
        }
        self.copied_messages.append(payload)
        return SimpleNamespace(message_id=self._next_message_id())

    async def send_photo(self, chat_id, photo, **kwargs):
        message = SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=self._next_message_id())
        self.sent_photos.append({"chat_id": chat_id, "photo": photo, "kwargs": kwargs})
        return message

    async def send_document(self, chat_id, document, **kwargs):
        message = SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=self._next_message_id())
        self.sent_documents.append({"chat_id": chat_id, "document": document, "kwargs": kwargs})
        return message

    async def post_logging_message(self, msg):
        self.posted_logs.append(msg)
        return True

    async def set_my_commands(self, commands, scope=None, **kwargs):
        self.set_commands_calls.append({"commands": commands, "scope": scope, "kwargs": kwargs})
        return True

    async def unpin_chat_message(self, chat_id, **kwargs):
        self.unpinned_chats.append({"chat_id": chat_id, "kwargs": kwargs})
        return True

    async def get_file(self, file_id):
        return SimpleNamespace(file_path=f"fake/{file_id}.jpg")

    async def download_file(self, file_path):
        return BytesIO(b"fake-file")

    def remove_markup_after(self, messages, timeout):
        return None

    def delete_messages_after(self, messages, timeout):
        return None


class TaskTracker:
    def __init__(self, *, create_task, sleep):
        self._create_task = create_task
        self._sleep = sleep
        self.tasks = []

    def create_task(self, coro):
        task = self._create_task(coro)
        self.tasks.append(task)
        return task

    async def drain(self):
        while True:
            pending = [task for task in self.tasks if not task.done()]
            if not pending:
                break
            await asyncio.gather(*pending)
            await self._sleep(0)
