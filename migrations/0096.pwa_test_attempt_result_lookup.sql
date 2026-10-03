-- depends: 0095.pwa_test_attempt_projection
-- effective_results resolves the current projection for every historical
-- result.  Keep that lookup indexed so a Staff statistics read cannot hold a
-- scarce SQLite read slot while scanning all attempts once per result.
create index test_attempts_result_idx on test_attempts (result_id);
