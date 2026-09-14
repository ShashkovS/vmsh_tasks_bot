# Векторные шахматные фигуры — 14 сентября 2026

Реализован [контракт](../docs/tikz-chess.md): 12 нативных TikZ-фигур с прежними
именами и координатами, без PNG и специальных шрифтов. Использованы контуры
авторского комплекта фигур. Санитайзер SVG и конвертер не изменены.

Проверки: 99 passed (`pytest -n 2` для `test_tikz_chess.py`,
`test_content_tikz.py`, `test_content_compiler.py`, `test_tikz_chess_smoke.py`).
Реальные pdfLaTeX и pdf2svg скомпилировали пример с шестью ладьями и все 12
фигур; проверены отсутствие `<image>` и растровых data URI, масштаб ×2 и
очистка временной папки. Снимки просмотрены визуально. Ruff и diff-check
прошли. Проверка загрузки на production не выполнялась.

## Все фигуры

![Все фигуры](assets/tikz-chess/all-pieces.png)

[Векторный SVG](assets/tikz-chess/all-pieces.svg).

## Исходный пример с ладьями

![Ладьи](assets/tikz-chess/rooks.png)

[Векторный SVG](assets/tikz-chess/rooks.svg).
