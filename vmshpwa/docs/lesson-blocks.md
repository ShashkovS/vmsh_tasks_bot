# Lesson blocks before and after tasks

`lesson_blocks` adds two optional, group-owned reading surfaces to one group
lesson: `before` appears below the lesson heading and `after` appears below the
worksheet. They have no content classification: teachers can put theory,
recordings or any other study material in either position.

## Authoring and publication

Staff with `content.manage` for the group save immutable Markdown revisions
through `StaffLessonBlocksEditor` in
[`apps/staff/src/staff-lesson-block-editor.tsx`](../apps/staff/src/staff-lesson-block-editor.tsx).
The draft, public revision and optional pending revision are independent.
Publishing can happen now, at a UTC timestamp, or when a browser-readable
condition is published. Hiding clears both public and pending pointers while
preserving the draft. `lesson_block_events` records each state transition.

The Staff API is in
[`apps/pwa_api/lesson_block_routes.py`](../../apps/pwa_api/lesson_block_routes.py):
`GET/PUT /staff/api/v1/group-lessons/{id}/blocks`, position-specific publication
and hide routes, plus a group-scoped image upload route. Every mutable route
requires the position ETag. Scheduled activation uses the existing content
scheduler in [`apps/pwa_app.py`](../../apps/pwa_app.py) and never creates
notifications.

## Markdown, images and videos

Lesson documents use the normal Rich Markdown subset plus root-level video
blocks. Images use the existing server-copy pipeline. The parser accepts:

```md
::video[Recording title](https://youtu.be/FTXGKbAk9To?t=90)
::video[Разбор](https://vkvideo.ru/video_ext.php?oid=-241691838&id=456239017&hd=2)
```

It also accepts a standalone YouTube or VK iframe and extracts only its `src`
and optional title. Raw iframe HTML is never stored or rendered. The browser
creates an iframe only after the reader selects “Загрузить видео”. Production
CSP permits only the canonical YouTube and VK Video frame origins.

`packages/contracts/src/lesson-rich-document.ts` and
`models/pwa/lesson_rich_document.py` validate the same normalized AST. News and
group banners continue using their stricter video-free RichDocument contract.

## Reader and print behavior

A published block makes an active lesson visible even when conditions are not
yet published. In that state `materials.condition` is unavailable,
`problemCount` is zero, no task query is made, and the view says “Задачи ещё не
опубликованы”. Student, Family and Staff reads retain their existing course,
group and child ownership checks.

`LessonBlocksLayout` in
[`packages/product/src/lesson-blocks.tsx`](../packages/product/src/lesson-blocks.tsx)
renders the same document around Student and Family worksheets. It namespaces
footnotes through `RichDocumentView`. Browser printing keeps the text and
canonical video link while hiding the live iframe.

The feature’s persistence migration is
[`migrations/0100.pwa_lesson_blocks.sql`](../../migrations/0100.pwa_lesson_blocks.sql).
