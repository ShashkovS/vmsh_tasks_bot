-- depends: 0108.pwa_problem_release
-- MATCH-04 in vmshpwa/dev/development-plan/06-phase-2-content.md.
-- Preserve historical rows while giving a fresh set independent IDs/slots.
CREATE TABLE content_problem_slots (
    problem_id INTEGER PRIMARY KEY REFERENCES problems(id),
    display_item TEXT NOT NULL,
    created_by_revision_id INTEGER REFERENCES content_revisions(id),
    retired_by_revision_id INTEGER REFERENCES content_revisions(id),
    created_at TEXT NOT NULL,
    created_by_user_id INTEGER REFERENCES users(id)
);

CREATE VIEW problem_catalog AS
SELECT p.id, p.group_id, p.lesson, p.prob,
       coalesce(slot.display_item, p.item) AS item,
       p.title, p.prob_text, p.prob_type, p.ans_type, p.ans_validation,
       p.validation_error, p.cor_ans, p.cor_ans_checker, p.wrong_ans,
       p.congrat, p.synonyms, 'p-' || p.id AS public_id
FROM problems p LEFT JOIN content_problem_slots slot ON slot.problem_id = p.id;

CREATE VIEW active_problems AS
SELECT p.* FROM problem_catalog p
WHERE NOT EXISTS (
    SELECT 1 FROM content_problem_slots slot
    WHERE slot.problem_id = p.id AND slot.retired_by_revision_id IS NOT NULL
);
