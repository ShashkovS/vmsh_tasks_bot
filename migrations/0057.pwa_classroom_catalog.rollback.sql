-- depends: 0056.pwa_support_threads

drop trigger classroom_events_delete_forbidden;
drop trigger classroom_events_immutable_update;
drop index classroom_events_timeline_idx;
drop table classroom_events;

drop trigger classrooms_delete_forbidden;
drop index classrooms_status_name_idx;
drop table classrooms;
