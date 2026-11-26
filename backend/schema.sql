-- =====================================================================
-- ProjectFlow database schema
-- PostgreSQL 15 or newer (uses ON DELETE SET NULL (column) on composite FKs)
--
-- Areas:
--   1. Identity and workspace   users, refresh_tokens, password_resets,
--                               workspaces, memberships, invitations, holidays
--   2. Projects and tasks       projects, sprints, tasks, dependencies,
--                               labels, task_labels
--   3. Collaboration            comments, comment_mentions, time_entries,
--                               attachments
--   4. Audit and reporting      notifications, activity_log, baselines,
--                               baseline_tasks
--
-- Conventions
--   * uuid primary keys (gen_random_uuid), bigint identity for activity_log
--   * timestamptz for moments, date for plan days
--   * text + CHECK for fixed value sets (easy to change in Alembic)
--   * every table with updated_at gets the set_updated_at trigger
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS citext;

-- ---------------------------------------------------------------------
-- Shared trigger functions
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

-- =====================================================================
-- 1. IDENTITY AND WORKSPACE
-- =====================================================================

CREATE TABLE users (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    email              citext      NOT NULL,
    password_hash      text        NOT NULL,
    full_name          text        NOT NULL,
    avatar_url         text,
    timezone           text        NOT NULL DEFAULT 'UTC',
    email_verified_at  timestamptz,
    last_login_at      timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_email_key UNIQUE (email),
    CONSTRAINT users_email_format CHECK (email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
    CONSTRAINT users_full_name_len CHECK (char_length(btrim(full_name)) BETWEEN 1 AND 120)
);

-- One row per issued refresh token. Rotation: each use revokes the row and
-- points replaced_by at the new one. Reuse of a revoked token => revoke the
-- whole family_id (stolen token detection).
CREATE TABLE refresh_tokens (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    family_id    uuid        NOT NULL,
    token_hash   text        NOT NULL,
    expires_at   timestamptz NOT NULL,
    revoked_at   timestamptz,
    replaced_by  uuid        REFERENCES refresh_tokens (id) ON DELETE SET NULL,
    user_agent   text,
    ip_address   inet,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT refresh_tokens_token_hash_key UNIQUE (token_hash)
);
CREATE INDEX refresh_tokens_user_idx   ON refresh_tokens (user_id);
CREATE INDEX refresh_tokens_family_idx ON refresh_tokens (family_id);

CREATE TABLE password_resets (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_hash  text        NOT NULL,
    expires_at  timestamptz NOT NULL,
    used_at     timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT password_resets_token_hash_key UNIQUE (token_hash)
);
CREATE INDEX password_resets_user_idx ON password_resets (user_id);

-- A workspace is the company boundary. Its calendar drives the scheduler.
CREATE TABLE workspaces (
    id             uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    name           text         NOT NULL,
    slug           text         NOT NULL,
    -- ISO weekdays: 1 = Monday ... 7 = Sunday
    working_days   smallint[]   NOT NULL DEFAULT '{1,2,3,4,5}',
    hours_per_day  numeric(4,2) NOT NULL DEFAULT 8,
    timezone       text         NOT NULL DEFAULT 'UTC',
    created_by     uuid         REFERENCES users (id) ON DELETE SET NULL,
    created_at     timestamptz  NOT NULL DEFAULT now(),
    updated_at     timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT workspaces_slug_key UNIQUE (slug),
    CONSTRAINT workspaces_slug_format CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND char_length(slug) <= 48),
    CONSTRAINT workspaces_name_len CHECK (char_length(btrim(name)) BETWEEN 1 AND 80),
    CONSTRAINT workspaces_working_days_valid CHECK (
        cardinality(working_days) BETWEEN 1 AND 7
        AND working_days <@ '{1,2,3,4,5,6,7}'::smallint[]
    ),
    CONSTRAINT workspaces_hours_per_day_range CHECK (hours_per_day > 0 AND hours_per_day <= 24)
);

CREATE TABLE memberships (
    workspace_id  uuid        NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    user_id       uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    role          text        NOT NULL,
    joined_at     timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT memberships_pkey PRIMARY KEY (workspace_id, user_id),
    CONSTRAINT memberships_role_valid CHECK (role IN ('owner', 'member', 'viewer'))
);
CREATE INDEX memberships_user_idx ON memberships (user_id);

-- A workspace must always keep at least one owner (unless the workspace
-- itself is being deleted).
CREATE OR REPLACE FUNCTION keep_one_owner() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.role = 'owner'
       AND (TG_OP = 'DELETE' OR NEW.role <> 'owner')
       AND EXISTS (SELECT 1 FROM workspaces w WHERE w.id = OLD.workspace_id)
       AND NOT EXISTS (
            SELECT 1 FROM memberships m
             WHERE m.workspace_id = OLD.workspace_id
               AND m.role = 'owner'
               AND m.user_id <> OLD.user_id)
    THEN
        RAISE EXCEPTION 'workspace % must keep at least one owner', OLD.workspace_id
            USING ERRCODE = 'check_violation', CONSTRAINT = 'memberships_last_owner';
    END IF;
    RETURN NULL;
END;
$$;
CREATE TRIGGER memberships_keep_one_owner
    AFTER UPDATE OF role OR DELETE ON memberships
    FOR EACH ROW EXECUTE FUNCTION keep_one_owner();

CREATE TABLE invitations (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  uuid        NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    email         citext      NOT NULL,
    role          text        NOT NULL,
    token_hash    text        NOT NULL,
    invited_by    uuid        REFERENCES users (id) ON DELETE SET NULL,
    expires_at    timestamptz NOT NULL,
    accepted_at   timestamptz,
    accepted_by   uuid        REFERENCES users (id) ON DELETE SET NULL,
    revoked_at    timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT invitations_token_hash_key UNIQUE (token_hash),
    CONSTRAINT invitations_role_valid CHECK (role IN ('owner', 'member', 'viewer')),
    CONSTRAINT invitations_single_outcome CHECK (accepted_at IS NULL OR revoked_at IS NULL)
);
-- At most one open invitation per email per workspace. The service revokes
-- an expired one before issuing a new one.
CREATE UNIQUE INDEX invitations_one_open_idx
    ON invitations (workspace_id, email)
    WHERE accepted_at IS NULL AND revoked_at IS NULL;

CREATE TABLE holidays (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  uuid        NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    holiday_date  date        NOT NULL,
    name          text        NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT holidays_one_per_day UNIQUE (workspace_id, holiday_date),
    CONSTRAINT holidays_name_len CHECK (char_length(btrim(name)) BETWEEN 1 AND 80)
);

-- =====================================================================
-- 2. PROJECTS AND TASKS
-- =====================================================================

CREATE TABLE projects (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        uuid        NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    key                 text        NOT NULL,           -- e.g. WEB, used in task keys WEB-24
    name                text        NOT NULL,
    description         text,
    start_date          date        NOT NULL,
    target_end_date     date        NOT NULL,
    is_template         boolean     NOT NULL DEFAULT false,
    -- engine output, rewritten on every recalculation
    projected_end_date  date,
    scheduled_at        timestamptz,
    -- next number handed to a new task; UPDATE ... RETURNING also locks the row
    next_task_number    integer     NOT NULL DEFAULT 1,
    archived_at         timestamptz,
    created_by          uuid        REFERENCES users (id) ON DELETE SET NULL,
    version             integer     NOT NULL DEFAULT 1,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT projects_workspace_id_id_key UNIQUE (workspace_id, id),
    CONSTRAINT projects_key_per_workspace UNIQUE (workspace_id, key),
    CONSTRAINT projects_key_format CHECK (key ~ '^[A-Z][A-Z0-9]{1,9}$'),
    CONSTRAINT projects_name_len CHECK (char_length(btrim(name)) BETWEEN 1 AND 120),
    CONSTRAINT projects_dates_order CHECK (target_end_date >= start_date),
    CONSTRAINT projects_next_task_number_positive CHECK (next_task_number > 0)
);
CREATE INDEX projects_active_idx ON projects (workspace_id, name) WHERE archived_at IS NULL;

CREATE TABLE sprints (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  uuid        NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    name        text        NOT NULL,
    goal        text,
    start_date  date        NOT NULL,
    end_date    date        NOT NULL,
    status      text        NOT NULL DEFAULT 'planned',
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT sprints_project_id_id_key UNIQUE (project_id, id),
    CONSTRAINT sprints_status_valid CHECK (status IN ('planned', 'active', 'completed')),
    CONSTRAINT sprints_dates_order CHECK (end_date >= start_date)
);
CREATE UNIQUE INDEX sprints_one_active_idx ON sprints (project_id) WHERE status = 'active';

CREATE TABLE tasks (
    id                     uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id           uuid         NOT NULL,
    project_id             uuid         NOT NULL,
    parent_id              uuid,
    sprint_id              uuid,
    number                 integer      NOT NULL,          -- WEB-<number>
    kind                   text         NOT NULL DEFAULT 'task',
    title                  text         NOT NULL,
    description            text,
    owner_id               uuid,
    status                 text         NOT NULL DEFAULT 'todo',
    priority               text         NOT NULL DEFAULT 'medium',
    estimate               numeric(7,2) NOT NULL DEFAULT 0,
    estimate_unit          text         NOT NULL DEFAULT 'days',
    -- set when someone drags a bar: the task may not start before this day
    start_no_earlier_than  date,
    -- fractional index for order inside a board column (compare with COLLATE "C")
    position               text         COLLATE "C" NOT NULL,
    -- engine output, rewritten on every recalculation
    scheduled_start        date,
    scheduled_end          date,
    slack_days             integer,
    is_critical            boolean      NOT NULL DEFAULT false,
    started_at             timestamptz,
    completed_at           timestamptz,
    deleted_at             timestamptz,
    created_by             uuid         REFERENCES users (id) ON DELETE SET NULL,
    version                integer      NOT NULL DEFAULT 1,
    created_at             timestamptz  NOT NULL DEFAULT now(),
    updated_at             timestamptz  NOT NULL DEFAULT now(),

    -- targets for composite foreign keys from other tables
    CONSTRAINT tasks_workspace_id_id_key UNIQUE (workspace_id, id),
    CONSTRAINT tasks_project_id_id_key   UNIQUE (project_id, id),
    CONSTRAINT tasks_number_per_project  UNIQUE (project_id, number),

    -- the project must be in the same workspace as the task
    CONSTRAINT tasks_project_fkey FOREIGN KEY (workspace_id, project_id)
        REFERENCES projects (workspace_id, id) ON DELETE CASCADE,
    -- a parent must be in the same project
    CONSTRAINT tasks_parent_fkey FOREIGN KEY (project_id, parent_id)
        REFERENCES tasks (project_id, id) ON DELETE CASCADE,
    -- a sprint must be in the same project
    CONSTRAINT tasks_sprint_fkey FOREIGN KEY (project_id, sprint_id)
        REFERENCES sprints (project_id, id) ON DELETE SET NULL (sprint_id),
    -- the owner must be a member of the workspace; removing the member unassigns
    CONSTRAINT tasks_owner_fkey FOREIGN KEY (workspace_id, owner_id)
        REFERENCES memberships (workspace_id, user_id) ON DELETE SET NULL (owner_id),

    CONSTRAINT tasks_number_positive   CHECK (number > 0),
    CONSTRAINT tasks_kind_valid        CHECK (kind IN ('task', 'milestone')),
    CONSTRAINT tasks_title_len         CHECK (char_length(btrim(title)) BETWEEN 1 AND 200),
    CONSTRAINT tasks_status_valid      CHECK (status IN ('todo', 'in_progress', 'in_review', 'done')),
    CONSTRAINT tasks_priority_valid    CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    CONSTRAINT tasks_estimate_unit_valid CHECK (estimate_unit IN ('hours', 'days')),
    CONSTRAINT tasks_estimate_range    CHECK (estimate >= 0 AND estimate <= 9999),
    CONSTRAINT tasks_milestone_no_estimate CHECK (kind = 'task' OR estimate = 0),
    CONSTRAINT tasks_not_own_parent    CHECK (parent_id IS NULL OR parent_id <> id),
    CONSTRAINT tasks_schedule_order    CHECK (scheduled_start IS NULL OR scheduled_end IS NULL
                                              OR scheduled_end >= scheduled_start),
    CONSTRAINT tasks_slack_nonnegative CHECK (slack_days IS NULL OR slack_days >= 0),
    CONSTRAINT tasks_done_has_completed_at CHECK ((status = 'done') = (completed_at IS NOT NULL))
);
-- Board: one column, in order
CREATE INDEX tasks_board_idx   ON tasks (project_id, status, position) WHERE deleted_at IS NULL;
-- Workload: one person's open tasks overlapping a date range
CREATE INDEX tasks_owner_schedule_idx ON tasks (owner_id, scheduled_start, scheduled_end)
    WHERE deleted_at IS NULL AND status <> 'done';
-- Dashboard: overdue tasks in a project
CREATE INDEX tasks_open_by_end_idx ON tasks (project_id, scheduled_end)
    WHERE deleted_at IS NULL AND status <> 'done';
CREATE INDEX tasks_parent_idx  ON tasks (parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX tasks_sprint_idx  ON tasks (sprint_id) WHERE sprint_id IS NOT NULL;

-- Subtasks go one level deep: a subtask cannot have subtasks, and a task
-- that has subtasks cannot become a subtask. This also rules out parent loops.
CREATE OR REPLACE FUNCTION enforce_subtask_depth() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.parent_id IS NOT NULL THEN
        IF EXISTS (SELECT 1 FROM tasks p WHERE p.id = NEW.parent_id AND p.parent_id IS NOT NULL) THEN
            RAISE EXCEPTION 'a subtask cannot have subtasks'
                USING ERRCODE = 'check_violation', CONSTRAINT = 'tasks_subtask_depth';
        END IF;
        IF EXISTS (SELECT 1 FROM tasks c WHERE c.parent_id = NEW.id) THEN
            RAISE EXCEPTION 'a task that has subtasks cannot become a subtask'
                USING ERRCODE = 'check_violation', CONSTRAINT = 'tasks_subtask_depth';
        END IF;
        IF EXISTS (SELECT 1 FROM tasks p WHERE p.id = NEW.parent_id AND p.kind = 'milestone') THEN
            RAISE EXCEPTION 'a milestone cannot have subtasks'
                USING ERRCODE = 'check_violation', CONSTRAINT = 'tasks_subtask_depth';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tasks_enforce_subtask_depth
    BEFORE INSERT OR UPDATE OF parent_id ON tasks
    FOR EACH ROW EXECUTE FUNCTION enforce_subtask_depth();

-- "successor cannot start until predecessor is done" (finish-to-start)
CREATE TABLE dependencies (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid        NOT NULL,
    predecessor_id  uuid        NOT NULL,
    successor_id    uuid        NOT NULL,
    created_by      uuid        REFERENCES users (id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    -- both ends must be tasks of this project
    CONSTRAINT dependencies_predecessor_fkey FOREIGN KEY (project_id, predecessor_id)
        REFERENCES tasks (project_id, id) ON DELETE CASCADE,
    CONSTRAINT dependencies_successor_fkey FOREIGN KEY (project_id, successor_id)
        REFERENCES tasks (project_id, id) ON DELETE CASCADE,
    CONSTRAINT dependencies_pair_key UNIQUE (predecessor_id, successor_id),
    CONSTRAINT dependencies_not_self CHECK (predecessor_id <> successor_id)
);
CREATE INDEX dependencies_successor_idx ON dependencies (successor_id);
CREATE INDEX dependencies_project_idx   ON dependencies (project_id);

-- Backstop for loops. The service checks first and builds a friendly message
-- with task keys; this trigger guarantees no loop is ever stored, even under
-- concurrent inserts, because it locks the project row before looking.
CREATE OR REPLACE FUNCTION prevent_dependency_cycle() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    loop_path uuid[];
BEGIN
    -- serialise link changes per project (READ COMMITTED: the query below
    -- takes a fresh snapshot after the lock, so it sees committed links)
    PERFORM 1 FROM projects WHERE id = NEW.project_id FOR UPDATE;

    -- can the new successor already reach the new predecessor?
    WITH RECURSIVE reach(task_id, path) AS (
        SELECT d.successor_id, ARRAY[NEW.successor_id, d.successor_id]
          FROM dependencies d
         WHERE d.predecessor_id = NEW.successor_id
        UNION ALL
        SELECT d.successor_id, r.path || d.successor_id
          FROM reach r
          JOIN dependencies d ON d.predecessor_id = r.task_id
         WHERE NOT d.successor_id = ANY (r.path)
    )
    SELECT path INTO loop_path FROM reach WHERE task_id = NEW.predecessor_id LIMIT 1;

    IF loop_path IS NOT NULL THEN
        RAISE EXCEPTION 'dependency would create a loop'
            USING ERRCODE = 'check_violation',
                  CONSTRAINT = 'dependencies_no_cycle',
                  DETAIL = array_to_string(NEW.predecessor_id || loop_path, ' -> ');
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER dependencies_prevent_cycle
    BEFORE INSERT OR UPDATE OF predecessor_id, successor_id ON dependencies
    FOR EACH ROW EXECUTE FUNCTION prevent_dependency_cycle();

CREATE TABLE labels (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  uuid        NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    name          text        NOT NULL,
    color         text        NOT NULL DEFAULT '#64748B',
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT labels_workspace_id_id_key UNIQUE (workspace_id, id),
    CONSTRAINT labels_name_per_workspace UNIQUE (workspace_id, name),
    CONSTRAINT labels_name_len CHECK (char_length(btrim(name)) BETWEEN 1 AND 40),
    CONSTRAINT labels_color_hex CHECK (color ~ '^#[0-9A-Fa-f]{6}$')
);

CREATE TABLE task_labels (
    workspace_id  uuid NOT NULL,
    task_id       uuid NOT NULL,
    label_id      uuid NOT NULL,
    CONSTRAINT task_labels_pkey PRIMARY KEY (task_id, label_id),
    CONSTRAINT task_labels_task_fkey FOREIGN KEY (workspace_id, task_id)
        REFERENCES tasks (workspace_id, id) ON DELETE CASCADE,
    CONSTRAINT task_labels_label_fkey FOREIGN KEY (workspace_id, label_id)
        REFERENCES labels (workspace_id, id) ON DELETE CASCADE
);
CREATE INDEX task_labels_label_idx ON task_labels (label_id);

-- =====================================================================
-- 3. COLLABORATION
-- =====================================================================

CREATE TABLE comments (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id     uuid        NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    author_id   uuid        REFERENCES users (id) ON DELETE SET NULL,
    body        text        NOT NULL,
    edited_at   timestamptz,
    deleted_at  timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT comments_body_len CHECK (char_length(btrim(body)) BETWEEN 1 AND 10000)
);
CREATE INDEX comments_task_idx ON comments (task_id, created_at);

-- Filled by the service when it parses @mentions out of a comment body.
CREATE TABLE comment_mentions (
    comment_id  uuid NOT NULL REFERENCES comments (id) ON DELETE CASCADE,
    user_id     uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT comment_mentions_pkey PRIMARY KEY (comment_id, user_id)
);
CREATE INDEX comment_mentions_user_idx ON comment_mentions (user_id);

CREATE TABLE time_entries (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id     uuid        NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    user_id     uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    work_date   date        NOT NULL,
    minutes     integer     NOT NULL,
    note        text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT time_entries_minutes_range CHECK (minutes BETWEEN 1 AND 1440)
);
CREATE INDEX time_entries_task_idx ON time_entries (task_id);
CREATE INDEX time_entries_user_day_idx ON time_entries (user_id, work_date);

CREATE TABLE attachments (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id       uuid        NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    uploaded_by   uuid        REFERENCES users (id) ON DELETE SET NULL,
    storage_key   text        NOT NULL,       -- object key in S3-compatible storage
    file_name     text        NOT NULL,
    content_type  text        NOT NULL,
    size_bytes    bigint      NOT NULL,
    deleted_at    timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT attachments_storage_key_key UNIQUE (storage_key),
    CONSTRAINT attachments_size_range CHECK (size_bytes > 0 AND size_bytes <= 26214400),  -- 25 MB
    CONSTRAINT attachments_file_name_len CHECK (char_length(file_name) BETWEEN 1 AND 255)
);
CREATE INDEX attachments_task_idx ON attachments (task_id) WHERE deleted_at IS NULL;

-- =====================================================================
-- 4. AUDIT AND REPORTING
-- =====================================================================

CREATE TABLE notifications (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  uuid        NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    recipient_id  uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    actor_id      uuid        REFERENCES users (id) ON DELETE SET NULL,
    type          text        NOT NULL,
    project_id    uuid        REFERENCES projects (id) ON DELETE CASCADE,
    task_id       uuid        REFERENCES tasks (id) ON DELETE CASCADE,
    comment_id    uuid        REFERENCES comments (id) ON DELETE CASCADE,
    data          jsonb       NOT NULL DEFAULT '{}'::jsonb,
    -- stops repeats, e.g. 'predecessor_late:<task id>:<scheduled_end>'
    dedupe_key    text,
    read_at       timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT notifications_type_valid CHECK (type IN (
        'task_assigned', 'mentioned', 'predecessor_late', 'task_overdue',
        'project_late', 'invited', 'role_changed'))
);
CREATE INDEX notifications_inbox_idx  ON notifications (recipient_id, created_at DESC);
CREATE INDEX notifications_unread_idx ON notifications (recipient_id) WHERE read_at IS NULL;
CREATE UNIQUE INDEX notifications_dedupe_idx ON notifications (recipient_id, dedupe_key)
    WHERE dedupe_key IS NOT NULL;

-- Append-only: who changed what, and when. No FK on entity_id or task_id so
-- history outlives the rows it describes.
CREATE TABLE activity_log (
    id            bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workspace_id  uuid        NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    project_id    uuid        REFERENCES projects (id) ON DELETE CASCADE,
    task_id       uuid,
    actor_id      uuid        REFERENCES users (id) ON DELETE SET NULL,
    entity_type   text        NOT NULL,
    entity_id     uuid        NOT NULL,
    action        text        NOT NULL,
    -- {"field": {"old": ..., "new": ...}, ...}
    changes       jsonb       NOT NULL DEFAULT '{}'::jsonb,
    -- groups the rows written by one request (a slip that moved 12 tasks)
    request_id    uuid,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT activity_log_entity_type_valid CHECK (entity_type IN (
        'workspace', 'membership', 'invitation', 'holiday', 'project', 'sprint',
        'task', 'dependency', 'comment', 'attachment', 'time_entry', 'baseline')),
    CONSTRAINT activity_log_action_valid CHECK (action IN (
        'created', 'updated', 'deleted', 'restored', 'archived', 'unarchived',
        'moved', 'rescheduled'))
);
CREATE INDEX activity_log_project_idx   ON activity_log (project_id, created_at DESC);
CREATE INDEX activity_log_entity_idx    ON activity_log (entity_type, entity_id, created_at DESC);
CREATE INDEX activity_log_workspace_idx ON activity_log (workspace_id, created_at DESC);
CREATE INDEX activity_log_task_idx      ON activity_log (task_id, created_at DESC) WHERE task_id IS NOT NULL;

-- Rows are never edited. The one allowed change is actor_id becoming NULL
-- when a user account is deleted (the ON DELETE SET NULL above).
CREATE OR REPLACE FUNCTION activity_log_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (to_jsonb(NEW) - 'actor_id') IS DISTINCT FROM (to_jsonb(OLD) - 'actor_id')
       OR NEW.actor_id IS NOT NULL AND NEW.actor_id IS DISTINCT FROM OLD.actor_id THEN
        RAISE EXCEPTION 'activity_log is append-only'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER activity_log_append_only
    BEFORE UPDATE ON activity_log
    FOR EACH ROW EXECUTE FUNCTION activity_log_guard();

-- A frozen copy of the plan, compared later with what really happened.
CREATE TABLE baselines (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid        NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    name                text        NOT NULL,
    projected_end_date  date        NOT NULL,
    created_by          uuid        REFERENCES users (id) ON DELETE SET NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT baselines_name_per_project UNIQUE (project_id, name)
);

CREATE TABLE baseline_tasks (
    baseline_id    uuid         NOT NULL REFERENCES baselines (id) ON DELETE CASCADE,
    task_id        uuid         NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    title          text         NOT NULL,
    estimate       numeric(7,2) NOT NULL,
    estimate_unit  text         NOT NULL,
    planned_start  date,
    planned_end    date,
    is_critical    boolean      NOT NULL,
    CONSTRAINT baseline_tasks_pkey PRIMARY KEY (baseline_id, task_id)
);

-- ---------------------------------------------------------------------
-- updated_at triggers
-- ---------------------------------------------------------------------
CREATE TRIGGER users_set_updated_at        BEFORE UPDATE ON users        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER workspaces_set_updated_at   BEFORE UPDATE ON workspaces   FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER memberships_set_updated_at  BEFORE UPDATE ON memberships  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER projects_set_updated_at     BEFORE UPDATE ON projects     FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER sprints_set_updated_at      BEFORE UPDATE ON sprints      FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER tasks_set_updated_at        BEFORE UPDATE ON tasks        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER comments_set_updated_at     BEFORE UPDATE ON comments     FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER time_entries_set_updated_at BEFORE UPDATE ON time_entries FOR EACH ROW EXECUTE FUNCTION set_updated_at();
