# Phase 2 content compiler characterization

Этот отчёт воспроизводится из 54/54 записей golden manifest; compiler обрабатывает
30 TeX sources, а PDF/JSON остаются под общим manifest gate. Здесь нет условий,
названий задач, rendered HTML, Telegram-текста или URL assets — только hashes,
структурные счётчики и коды диагностик.

## Итог

- compiler: `vmsh-latex-compiler/1`;
- manifest: `vmshpwa/fixtures/content/golden-manifest.json`;
- manifest entries: 54;
- compiled TeX sources: 30;
- active problem AST nodes: 334;
- structural signal failures: 0;
- deterministic record-set SHA-256: `e3fb1388e21a561860cd3c6da615a6b2b01121e5b9a9cd2dd2d7046c2ec0a3c7`.

## Диагностики

- `warning:latex.layout_crosses_semantic_boundary`: 1

Единственное ожидаемое предупреждение относится к legacy print-layout, который
пересекает semantic boundary в одном solution source. Семантические поля при
этом сохранены; ошибок compiler и утечек соседних material branches нет.

## Проверка

```text
.venv/bin/python vmshpwa/scripts/content_characterization.py check
.venv/bin/pytest -q pwa_tests/domain/test_content_compiler.py pwa_tests/domain/test_telegram_rich.py
```

Машиночитаемые per-source hashes и counters находятся в
`pwa_tests/reports/phase2-content-compiler.json`; они не дублируют содержимое
golden corpus.
