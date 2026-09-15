-- depends: 0084.pwa_iterative_analytics
CREATE TABLE staff_test_students (
    staff_account_id INTEGER PRIMARY KEY REFERENCES auth_accounts(id),
    student_user_id INTEGER NOT NULL UNIQUE REFERENCES users(id)
);
