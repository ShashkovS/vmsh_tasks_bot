# Phase 1 auth race and Argon2 resource hardening proof

Дата: 27 июля 2026 года.

Этот proof закрывает три найденных после основного realtime-инкремента
security/ordering regression, не меняя refresh replay semantics:

- отзыв session между access-cookie auth и process-local WebSocket register;
- invalidation до `connected|resync-required` либо потеря на том же cursor;
- дешёвый parse-failure для malformed или чрезмерно дорогого stored Argon2id
  вместо полного dummy verify неизвестного login.

## Исполнимые инварианты

- `close_session` сначала создаёт process-local tombstone и лишь затем ищет
  sockets. Поэтому уже полученная close-команда не может быть пропущена
  последующей регистрацией того же случайного, непереиспользуемого session ID.
- WebSocket регистрируется pending: session/account close видит его, но
  audience/account/session fan-out не отправляет ему application events.
- После register выполняется authoritative SQLite revalidation. Первый frame и
  переход в routable выполняются под тем же per-audience cursor/broadcast lock,
  под которым выделяются invalidation cursors.
- Argon2 precheck принимает только Argon2id v16/v19 внутри generous envelope:
  encoding не длиннее 1024 bytes, память до 262144 KiB, `time_cost` 1–10,
  `parallelism` 1–16, память не меньше `8 * parallelism`, salt 8–64 bytes и
  hash 4–128 bytes. Текущие production defaults (`m=65536,t=3,p=4`) входят с
  запасом; слабее настроенный, но допустимый legacy hash после успешного входа
  проходит штатный rehash.
- Malformed или out-of-policy active hash выбирает startup-precomputed dummy
  до вызова verifier. Даже совпадение с dummy не может авторизовать account,
  потому что пригодность исходного account hash проверяется отдельно.

## Регрессии и результаты

- `pwa_tests/test_websocket_sessions.py`: tombstone до register и отсутствие
  fan-out для pending connection до initial frame; уже выбранная отправка,
  ожидающая общей transport-capacity, повторно проверяет `closing` и не может
  пройти после победившего session revoke.
- `pwa_tests/test_pwa_app.py`: пока revalidation удерживается управляемым
  barrier, concurrent invalidation завершается, но pending socket не получает
  frame. Первым наблюдаемым сообщением становится `connected(cursor=1)`: уже
  завершившееся изменение поглощено initial full-state boundary, не потеряно и
  не пришло раньше handshake.
- `pwa_tests/integration/test_auth_http_api.py`: настоящий aiohttp + migrated
  SQLite; session отзывается и close выполняется в барьере между auth и
  register, после чего клиент не получает `connected`.
- `pwa_tests/test_auth_service.py`: unknown, malformed и syntactically valid
  out-of-policy hash проверяют instrumented вызовы и выбирают ровно один dummy
  verify. Wall-clock assertions отсутствуют.

Проверено:

- Ruff по изменённым Python-файлам — PASS;
- focused pure registry/auth service — **32 PASS**;
- focused aiohttp protocol/auth integration — **45 PASS**;
- полный `.venv/bin/pytest -q -n0 pwa_tests` — **808 PASS, 1 intentional
  skip**.

Production import/apply, server `nginx -t` и live rate-limit smoke этим proof не
выполнялись и остаются отдельными Phase-1 gates.
