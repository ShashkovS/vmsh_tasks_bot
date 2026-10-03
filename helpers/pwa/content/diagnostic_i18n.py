"""Localize compiler diagnostics on read, including historical stored revisions.

Templates mirror parser/compiler/TikZ diagnostics, keyed by stable code. Exact
source matching preserves unknown diagnostics and all author-supplied values.
Never use this projection for persistence: see 24-i18n-execution-plan.md P6.
"""

from __future__ import annotations

import re
from functools import cache
from string import Formatter

from helpers.pwa.i18n import N_, _, current_locale

TEMPLATES = {
    "compiler.internal_error": {
        "message": N_(
            "Внутренняя ошибка компилятора. Загрузите новую revision или обратитесь к администратору."
        ),
    },
    "compiler.persistence_failed": {
        "message": N_("Не удалось атомарно сохранить производные компиляции."),
    },
    "asset.missing": {
        "message": N_("Указанный рисунок отсутствует в переданной библиотеке assets."),
        "recovery": N_(
            "Сопоставьте существующий hash или загрузите недостающий asset."
        ),
    },
    "asset.reference_invalid": {
        "message": N_(
            "Имя asset пусто, выходит из логического namespace или содержит опасные символы."
        ),
        "recovery": N_(
            "Используйте относительное логическое имя без .., URL и абсолютного пути."
        ),
    },
    "asset.url_conflict": {
        "message": N_(
            "URL производного asset расходится с опубликованным typed descriptor."
        ),
        "recovery": N_(
            "Используйте один опубликованный descriptor для web и Telegram."
        ),
    },
    "asset.url_unsafe": {
        "message": N_(
            "URL производного asset использует запрещённую схему или authority."
        ),
        "recovery": N_("Исправьте URL mapping для логического asset {value0}."),
    },
    "latex.announcement_empty": {
        "message": N_("Объявление не содержит отображаемого текста."),
        "recovery": N_("Добавьте текст объявления или удалите пустой блок."),
    },
    "latex.announcement_end_mismatch": {
        "message": N_("Команда \\{value0} не соответствует началу \\{value1}."),
        "recovery": N_("Используйте завершающую команду того же вида объявления."),
    },
    "latex.announcement_end_unexpected": {
        "message": N_("Завершающая команда \\{value0} не имеет начала объявления."),
        "recovery": N_(
            "Удалите лишнюю команду или добавьте соответствующее начало объявления."
        ),
    },
    "latex.announcement_nested": {
        "message": N_("Объявления нельзя вкладывать друг в друга."),
        "recovery": N_("Закройте текущее объявление до начала следующего."),
    },
    "latex.announcement_unclosed": {
        "message": N_("Объявление \\{value0} не имеет завершающей команды."),
        "recovery": N_(
            "Добавьте \\кобъявление для обычного или \\кважноеОбъявление для важного объявления."
        ),
    },
    "latex.argument_missing": {
        "message": N_("Команда \\{value0} не получила обязательную braced-группу."),
    },
    "latex.command_forbidden": {
        "message": N_("Команда \\{value0} запрещена в загружаемом content source."),
        "recovery": N_("Удалите файловый, динамический или output-примитив из source."),
    },
    "latex.dangling_backslash": {
        "message": N_("Одиночный обратный слеш не образует LaTeX-команду."),
        "recovery": N_("Удалите слеш или используйте \\\\ для переноса строки."),
    },
    "latex.document_fragment": {
        "message": N_(
            "Source не содержит оболочку \\begin{document}; разобран как фрагмент."
        ),
    },
    "latex.document_unclosed": {
        "message": N_("Не найдена завершающая команда \\end{document}."),
        "recovery": N_("Закройте document environment и повторите compile."),
    },
    "latex.environment_argument_missing": {
        "message": N_("Environment {value0} не содержит обязательные аргументы."),
    },
    "latex.environment_unclosed": {
        "message": N_("Environment {value0} не закрыт."),
    },
    "latex.environment_unsupported": {
        "message": N_("Environment {value0} не поддерживается compiler."),
        "recovery": N_(
            "Замените environment поддерживаемой структурой или добавьте parser fixture."
        ),
    },
    "latex.field_unclosed": {
        "message": N_("Блок {value0} не имеет завершающей команды."),
        "recovery": N_("Закройте блок соответствующей парной командой."),
    },
    "latex.group_depth": {
        "message": N_("Превышена максимальная глубина вложенности фигурных скобок."),
    },
    "latex.group_unclosed": {
        "message": N_("Не найдена закрывающая фигурная скобка."),
    },
    "latex.layout_crosses_semantic_boundary": {
        "message": N_(
            "Print-layout environment {value0} пересекает границу условия/подсказки/решения и не переносится в web AST."
        ),
        "recovery": N_(
            "Web renderer сохраняет semantic field blocks без печатной раскладки."
        ),
    },
    "latex.layout_group_crosses_semantic_boundary": {
        "message": N_(
            "Print-layout command \\{value0} пересекает границу условия/подсказки/решения и не переносится в web AST."
        ),
    },
    "latex.link_unsafe": {
        "message": N_("Ссылка использует запрещённую или некорректную схему URL."),
        "recovery": N_(
            "Используйте абсолютный HTTPS URL, mailto, tel или локальный #anchor."
        ),
    },
    "latex.list_without_items": {
        "message": N_("Список не содержит команд \\item."),
    },
    "latex.math_environment_empty": {
        "message": N_("Environment {value0} не содержит формулу."),
    },
    "latex.math_unclosed": {
        "message": N_("Не найдена закрывающая граница математической формулы."),
    },
    "latex.multicols_count_missing": {
        "message": N_("Environment 'multicols' не содержит число колонок."),
    },
    "latex.no_problems": {
        "message": N_("В источнике не найдено ни одной поддерживаемой команды задачи."),
        "recovery": N_("Используйте \\задача…\\кзадача или \\problem…\\eproblem."),
    },
    "latex.node_limit": {
        "message": N_("Документ превышает безопасный лимит структурных узлов."),
        "recovery": N_("Разделите материал на несколько source-файлов."),
    },
    "latex.picture_ignored": {
        "message": N_(
            "Legacy environment 'picture' пропущен до будущей конвертации в TikZ."
        ),
        "recovery": N_("Перенесите рисунок в TikZ для отображения в web-производной."),
    },
    "latex.problem_unclosed": {
        "message": N_("Задача не имеет явной завершающей команды."),
        "recovery": N_("Добавьте \\кзадача или \\eproblem."),
    },
    "latex.structure_in_inline_group": {
        "message": N_("Структурная команда \\{value0} вложена в inline-группу."),
        "recovery": N_("Вынесите конструкцию из команды форматирования."),
    },
    "latex.table_figure_layout_flattened": {
        "message": N_(
            "Табличная раскладка рисунков преобразована в последовательные web-блоки."
        ),
    },
    "latex.table_preamble_missing": {
        "message": N_("Таблица не содержит полного column preamble."),
    },
    "latex.tikz_preamble_ignored": {
        "message": N_("Команда \\tikzset не примыкает к TikZ и не включена в asset."),
        "recovery": N_(
            "Разместите локальный \\tikzset непосредственно перед \\begin{tikzpicture} или внутри % addToTikz-блока."
        ),
    },
    "latex.unknown_macro": {
        "message": N_("Команда \\{value0} не входит в поддерживаемый LaTeX-корпус."),
        "recovery": N_(
            "Замените команду поддерживаемой конструкцией или расширьте compiler с тестом."
        ),
    },
    "latex.verb_unclosed": {
        "message": N_("Команда \\verb не имеет завершающего delimiter."),
    },
    "material.parts_mismatch": {
        "message": N_("Задача {value0}: пункты материала не совпадают с условием."),
        "recovery": N_("Исправьте разметку пунктов перед публикацией."),
    },
    "source.replacement_character": {
        "message": N_(
            "Source содержит символ замены U+FFFD ({value0} вхождений) и уже повреждён до загрузки."
        ),
        "recovery": N_(
            "Восстановите исходный файл из корректной UTF-8/Windows-1251 копии; перекодирование текущих байтов не вернёт утраченные буквы."
        ),
    },
    "telegram.derivative_invalid": {
        "message": N_(
            "Telegram Rich derivative не прошёл allowlist/limits-проверку: {value0}"
        ),
        "recovery": N_("Исправьте AST renderer; отправка такого derivative запрещена."),
    },
    "tikz.add_to_tikz_unclosed": {
        "message": N_("Маркер % addToTikz не имеет парного закрывающего маркера."),
    },
    "tikz.context_declaration_malformed": {
        "message": N_("Не удалось разобрать объявление \\{value0}."),
    },
    "tikz.empty": {
        "message": N_("TikZ-блок пуст."),
    },
    "tikz.environment_unclosed": {
        "message": N_("Environment tikzpicture не закрыт."),
    },
    "tikz.inline_argument_missing": {
        "message": N_("Команда \\tikz не содержит braced-тело."),
    },
    "tikz.size_limit": {
        "message": N_("TikZ-блок превышает безопасный лимит размера."),
    },
    "web.derivative_invalid": {
        "message": N_("WebContentDocument v1 не прошёл contract boundary: {value0}"),
        "recovery": N_(
            "Исправьте AST adapter; публикация такого derivative запрещена."
        ),
    },
}


@cache
def _pattern(template: str):
    if "{value" not in template:
        return re.compile(re.escape(template)), False
    pattern = ""
    for literal, field, _format, _conversion in Formatter().parse(template):
        pattern += re.escape(literal)
        if field is not None:
            pattern += f"(?P<{field}>.*?)"
    return re.compile(pattern, re.DOTALL), True


def localize_diagnostics(items: list[object]) -> list[object]:
    if current_locale.get() == "ru":
        return items
    result = []
    for item in items:
        if not isinstance(item, dict):
            result.append(item)
            continue
        translated = dict(item)
        for field, template in TEMPLATES.get(item.get("code"), {}).items():
            value = item.get(field)
            if not isinstance(value, str):
                continue
            pattern, dynamic = _pattern(template)
            match = pattern.fullmatch(value)
            if match:
                translated[field] = (
                    _(template, **match.groupdict()) if dynamic else _(template)
                )
        result.append(translated)
    return result
