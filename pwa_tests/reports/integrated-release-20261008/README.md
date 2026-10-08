# Объединённый выпуск ВМШ / TLF — 2026-10-08

Оба production обновлены до `d4bf4a30ce9ddee3723fd13ed22eec95f9670ef0`.
[Deployment receipt](deployment.json), [решение владельца](owner-release-decision.json),
[состав и ограничения](../../../docs/performance/integrated-release-20261008.md).

- [ВМШ runtime/schema/backups](production-vmsh.json), [deploy log](deploy-vmsh.log),
  [25 HTTP checks](vmsh-http-after.log).
- [TLF runtime/schema/credentials/data](production-tlf.json), [deploy log](deploy-tlf.log),
  [rehearsal/guard/25 HTTP checks](tlf-verification.log).
- [Внешние JS/CSS/worker bytes, provenance и CSP](public-release.json).
- [Новый media domain: три объекта на обоих origins](vmsh-media-domain.json).
- [Первый TLF attempt](deploy-tlf-attempt1.log) остановился до maintenance/cutover:
  comparator не мог читать root-owned JSON. [Исправленный script](deploy-tlf.sh)
  выполнил отдельный retry `r2` с SHA-256 из deployment receipt.

**Общий release gate не зелёный.** Владелец выбрал выпуск после сообщения об
этом ограничении. Completed suites: format/types/lint/i18n, 2882 Python / 7 SKIP,
1068 frontend, 364 Storybook PASS. [Основная матрица](matrix-failures/release-gate.json):
385 PASS / 20 SKIP / 6 FAIL. Harness исправлен, focused reconnect 3 PASS и
[реальная SW activation](sw-real-button.json) 12 PASS в трёх engines.
Product code после `68eee3f6` не менялся. Figure/runtime/statistics/visual и
полный locale replay остаются follow-up после освобождения ресурсов Mac;
assertions/timeouts/retries/goldens не ослаблялись.

Исходные evidence сохранены: [невалидная квитанция первого interruption](initial-release-gate.json),
[причина последующих interruptions](resource-degradation.json),
[all-mode interruption](final-navigation-failures/interrupted-gate.json),
[focused FAIL](final-focused-failure/summary.json), [locale replay interruption](locale-reload-fixed-interrupted.json).
Невалидная zero-квитанция runner исправлена regression tests, не используется как PASS.

Direct S3 не включался: Beget не прошёл checksum/HEAD proof; browser WebP
использует лёгкий backend proxy без повторного кодирования. Ускорение на
production ещё не измерено. Runtime/credentials/production rows не переносятся
между порталами или из тестового контура.
