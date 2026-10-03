-- depends: 0085.pwa_staff_testing
-- Scoped completed-review lookup; vmshpwa/docs/review-history.md.
CREATE INDEX submission_reviews_reviewer_time_idx
    ON submission_reviews (reviewer_user_id, created_at DESC, id DESC);
CREATE INDEX problems_review_lesson_idx ON problems (group_id, lesson, id);
