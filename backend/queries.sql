-- ProjectFlow: the queries each screen runs, and the index each one uses.
-- :project, :me, :from, :to are bind parameters (shown here with psql \set).
\set project '''00000000-0000-0000-0000-000000000001'''
\set me      '''00000000-0000-0000-0000-000000000002'''
\set from    '''2026-11-16'''
\set to      '''2026-11-29'''

-- 1. Board: every open card, grouped by column, in drag order  (tasks_board_idx)
SELECT id, number, title, status, priority, owner_id, scheduled_end, is_critical, position
  FROM tasks
 WHERE project_id = :project AND deleted_at IS NULL
 ORDER BY status, position, id;

-- 2. Engine input: tasks and links of one project  (tasks_board_idx, dependencies_project_idx)
SELECT id, parent_id, kind, estimate, estimate_unit, start_no_earlier_than, status, completed_at
  FROM tasks WHERE project_id = :project AND deleted_at IS NULL;
SELECT predecessor_id, successor_id FROM dependencies WHERE project_id = :project;

-- 3. Workload: open tasks of the project's people overlapping the visible weeks
--    (tasks_owner_schedule_idx). Hours per day are spread in Python with the
--    same calendar code the engine uses.
SELECT t.owner_id, t.id, t.estimate, t.estimate_unit, t.scheduled_start, t.scheduled_end
  FROM tasks t
 WHERE t.project_id = :project
   AND t.owner_id IS NOT NULL
   AND t.deleted_at IS NULL AND t.status <> 'done'
   AND t.scheduled_start <= :to AND t.scheduled_end >= :from;

-- 4. Dashboard: % done, overdue, tasks per person  (tasks_open_by_end_idx)
SELECT count(*) FILTER (WHERE status = 'done')                       AS done,
       count(*)                                                      AS total,
       round(100.0 * count(*) FILTER (WHERE status = 'done') / NULLIF(count(*), 0), 1) AS pct_done,
       count(*) FILTER (WHERE status <> 'done' AND scheduled_end < current_date) AS overdue
  FROM tasks
 WHERE project_id = :project AND deleted_at IS NULL AND kind = 'task'
   AND NOT EXISTS (SELECT 1 FROM tasks c WHERE c.parent_id = tasks.id AND c.deleted_at IS NULL);

SELECT u.id, u.full_name, count(t.id) AS open_tasks
  FROM tasks t JOIN users u ON u.id = t.owner_id
 WHERE t.project_id = :project AND t.deleted_at IS NULL AND t.status <> 'done'
 GROUP BY u.id, u.full_name
 ORDER BY open_tasks DESC;

-- 5. Parent progress from subtasks  (tasks_parent_idx)
SELECT p.id,
       count(c.id) FILTER (WHERE c.status = 'done') AS done_subtasks,
       count(c.id)                                 AS subtasks
  FROM tasks p JOIN tasks c ON c.parent_id = p.id AND c.deleted_at IS NULL
 WHERE p.project_id = :project AND p.deleted_at IS NULL
 GROUP BY p.id;

-- 6. Bell icon: unread count and the latest 20  (notifications_unread_idx, notifications_inbox_idx)
SELECT count(*) FROM notifications WHERE recipient_id = :me AND read_at IS NULL;
SELECT id, type, actor_id, task_id, data, read_at, created_at
  FROM notifications WHERE recipient_id = :me
 ORDER BY created_at DESC LIMIT 20;

-- 7. "A task you wait on is late": successors of late, unfinished tasks, owner to notify
--    (tasks_open_by_end_idx, dependencies_pair_key). Insert with
--    dedupe_key = 'predecessor_late:' || pred.id || ':' || pred.scheduled_end
SELECT succ.owner_id AS recipient, pred.id AS late_task, succ.id AS waiting_task, pred.scheduled_end
  FROM tasks pred
  JOIN dependencies d ON d.predecessor_id = pred.id
  JOIN tasks succ      ON succ.id = d.successor_id
 WHERE pred.project_id = :project
   AND pred.deleted_at IS NULL AND pred.status <> 'done'
   AND pred.scheduled_end < current_date
   AND succ.owner_id IS NOT NULL AND succ.deleted_at IS NULL;

-- 8. Activity feed for a project, newest first, page by id  (activity_log_project_idx)
SELECT a.id, a.actor_id, a.entity_type, a.entity_id, a.action, a.changes, a.created_at
  FROM activity_log a
 WHERE a.project_id = :project
 ORDER BY a.created_at DESC, a.id DESC
 LIMIT 50;

-- 9. Next task number (also locks the project row for the rest of the transaction)
-- UPDATE projects SET next_task_number = next_task_number + 1
--  WHERE id = :project RETURNING next_task_number - 1 AS number;
