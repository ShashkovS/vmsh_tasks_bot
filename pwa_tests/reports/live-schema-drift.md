# Read-only live schema drift report

This report contains schema metadata only. Product row values were not selected
or stored. Live DDL/default literals were read transiently but are represented
only by safe structural metadata and fingerprints; paths and timestamps are omitted.

## Summary

- Expected product hash: `0743b36000b236e1c67aae02bc08739c29c0859d81e3ac025b51f91fa104a44a`.
- Observed product hash: `f87af9f4843dcffe35651780b8b77ab9d1137d54b588423af4a01aa138c981e8`.
- DDL text differences: 27.
- PRAGMA-structure differences: 4.
- Yoyo infrastructure hash: `9d5f0fd33d7ccfd7253ad2bcbee6294307bc625c646839e5d4fb5edc1a8e6ec5`.
- Repository migration head current: false.
- Known legacy-derived objects: 12.

## Migration-head drift

- Missing: `0039.pwa_auth_accounts_sessions`, `0040.pwa_courses_access`.
- Changed: none.
- Unexpected: none.

## Known schema defects

- `LIVE_REACTION_ENUM_TYPE_FK_MISSING` — reaction_type_id has no foreign key to reaction_type_enum.
- `LIVE_REACTIONS_ZOOM_FK_TARGET_INVALID` — zoom_conversation_id targets the absent zoom_conversation.zoom_conversation_id column.

## Legacy-derived objects

- `table temp_7_window` — structure `cb732b99efd18354cc1bb4b89f518203f652c634a03e660cf99368c93d51fbf0`.
- `table temp_7_window_3` — structure `cb1f154fa29990c3fdb97d2910f3112560660c5cf380455221039b08becd1b5f`.
- `table temp_from_excel` — structure `5858112b76ee8e802f733ad65fe128a46ef862d8f6518373708a7a3f19d1b789`.
- `table temp_lesson_scores` — structure `355e80c5203e5541892dfd863c38f748667c5e118da9b5c11a7d66168672d483`.
- `table temp_problem_scores` — structure `bbaab51586b5414296ca3a6d32a017d2e0da95415ed94de5cd6ccb7127397412`.
- `table temp_real_problem_scores` — structure `e0c3a895f578c3c48ffc30bea56c04ffd0e5e8d62456f4833f25dae156287dfd`.
- `table temp_result_rolling_window_scores` — structure `a95e489687394bdac7bdd6db9f7b9e6d60d658dfb9941db54b72ece93f457100`.
- `table temp_result_rolling_window_scores_3` — structure `9426885badf254e4eb32462d34182422d13155b1618bce2d671bf4689d98281d`.
- `table temp_student_visits` — structure `7e609ece8a755e9288bb4a1f9076acaa4009386e8180703ed7aff30f7ef469c2`.
- `table temp_students_ids` — structure `dae4a19f8de381c62d8e70a0376a24c502008cc51f6ca57eace700126f045261`.
- `table temp_user_decoder` — structure `a4c096e3d324544fe4356527573e0ad8f65cfaf1b06b46c29fd37320d62992e5`.
- `view temp_zoom_teacher_work` — structure `f1ab1de30ffb2ab1404f577d27dd38dfd6410ee9aeea153ebd156c001de6278d`.

## Data deliberately outside this check

- `0038.kv_logins` contains legacy rows. The schema inventory never
  selects, hashes or exports their values; synthetic test seeding must
  sanitize them in its own isolated database.
- Live DDL/default literals are never serialized. Persisted fingerprints
  detect drift in product, yoyo and allowlisted derived objects.

The exact JSON evidence is stored beside this document.
