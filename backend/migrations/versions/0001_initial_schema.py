"""initial schema: 21 tables, indexes, trigger functions and triggers

Revision ID: 0001
Revises: 
Create Date: 2026-11-16 22:15:59.442343

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FUNCTIONS = [
    r"""CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;""",
    r"""CREATE OR REPLACE FUNCTION keep_one_owner() RETURNS trigger
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
$$;""",
    r"""CREATE OR REPLACE FUNCTION enforce_subtask_depth() RETURNS trigger
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
$$;""",
    r"""CREATE OR REPLACE FUNCTION prevent_dependency_cycle() RETURNS trigger
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
$$;""",
    r"""CREATE OR REPLACE FUNCTION activity_log_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (to_jsonb(NEW) - 'actor_id') IS DISTINCT FROM (to_jsonb(OLD) - 'actor_id')
       OR NEW.actor_id IS NOT NULL AND NEW.actor_id IS DISTINCT FROM OLD.actor_id THEN
        RAISE EXCEPTION 'activity_log is append-only'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END;
$$;""",
]

TRIGGERS = [
    r"""CREATE TRIGGER memberships_keep_one_owner AFTER UPDATE OF role OR DELETE ON memberships FOR EACH ROW EXECUTE FUNCTION keep_one_owner();""",
    r"""CREATE TRIGGER tasks_enforce_subtask_depth BEFORE INSERT OR UPDATE OF parent_id ON tasks FOR EACH ROW EXECUTE FUNCTION enforce_subtask_depth();""",
    r"""CREATE TRIGGER dependencies_prevent_cycle BEFORE INSERT OR UPDATE OF predecessor_id, successor_id ON dependencies FOR EACH ROW EXECUTE FUNCTION prevent_dependency_cycle();""",
    r"""CREATE TRIGGER activity_log_append_only BEFORE UPDATE ON activity_log FOR EACH ROW EXECUTE FUNCTION activity_log_guard();""",
    r"""CREATE TRIGGER users_set_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();""",
    r"""CREATE TRIGGER workspaces_set_updated_at BEFORE UPDATE ON workspaces FOR EACH ROW EXECUTE FUNCTION set_updated_at();""",
    r"""CREATE TRIGGER memberships_set_updated_at BEFORE UPDATE ON memberships FOR EACH ROW EXECUTE FUNCTION set_updated_at();""",
    r"""CREATE TRIGGER projects_set_updated_at BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION set_updated_at();""",
    r"""CREATE TRIGGER sprints_set_updated_at BEFORE UPDATE ON sprints FOR EACH ROW EXECUTE FUNCTION set_updated_at();""",
    r"""CREATE TRIGGER tasks_set_updated_at BEFORE UPDATE ON tasks FOR EACH ROW EXECUTE FUNCTION set_updated_at();""",
    r"""CREATE TRIGGER comments_set_updated_at BEFORE UPDATE ON comments FOR EACH ROW EXECUTE FUNCTION set_updated_at();""",
    r"""CREATE TRIGGER time_entries_set_updated_at BEFORE UPDATE ON time_entries FOR EACH ROW EXECUTE FUNCTION set_updated_at();""",
]

FUNCTION_NAMES = ['set_updated_at', 'keep_one_owner', 'enforce_subtask_depth', 'prevent_dependency_cycle', 'activity_log_guard']


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    for ddl in FUNCTIONS:
        op.execute(ddl)
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('users',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('email', postgresql.CITEXT(), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('full_name', sa.Text(), nullable=False),
    sa.Column('avatar_url', sa.Text(), nullable=True),
    sa.Column('timezone', sa.Text(), server_default='UTC', nullable=False),
    sa.Column('email_verified_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('last_login_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("email ~ '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$'", name=op.f('users_email_format')),
    sa.CheckConstraint('char_length(btrim(full_name)) BETWEEN 1 AND 120', name=op.f('users_full_name_len')),
    sa.PrimaryKeyConstraint('id', name=op.f('users_pkey')),
    sa.UniqueConstraint('email', name='users_email_key')
    )
    op.create_table('password_resets',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.Text(), nullable=False),
    sa.Column('expires_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
    sa.Column('used_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('password_resets_user_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('password_resets_pkey')),
    sa.UniqueConstraint('token_hash', name='password_resets_token_hash_key')
    )
    op.create_index('password_resets_user_idx', 'password_resets', ['user_id'], unique=False)
    op.create_table('refresh_tokens',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('family_id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.Text(), nullable=False),
    sa.Column('expires_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
    sa.Column('revoked_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('replaced_by', sa.UUID(), nullable=True),
    sa.Column('user_agent', sa.Text(), nullable=True),
    sa.Column('ip_address', postgresql.INET(), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['replaced_by'], ['refresh_tokens.id'], name=op.f('refresh_tokens_replaced_by_fkey'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('refresh_tokens_user_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('refresh_tokens_pkey')),
    sa.UniqueConstraint('token_hash', name='refresh_tokens_token_hash_key')
    )
    op.create_index('refresh_tokens_family_idx', 'refresh_tokens', ['family_id'], unique=False)
    op.create_index('refresh_tokens_user_idx', 'refresh_tokens', ['user_id'], unique=False)
    op.create_table('workspaces',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('slug', sa.Text(), nullable=False),
    sa.Column('working_days', postgresql.ARRAY(sa.SmallInteger()), server_default=sa.text("'{1,2,3,4,5}'"), nullable=False),
    sa.Column('hours_per_day', sa.Numeric(precision=4, scale=2), server_default=sa.text('8'), nullable=False),
    sa.Column('timezone', sa.Text(), server_default='UTC', nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("cardinality(working_days) BETWEEN 1 AND 7 AND working_days <@ '{1,2,3,4,5,6,7}'::smallint[]", name=op.f('workspaces_working_days_valid')),
    sa.CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND char_length(slug) <= 48", name=op.f('workspaces_slug_format')),
    sa.CheckConstraint('char_length(btrim(name)) BETWEEN 1 AND 80', name=op.f('workspaces_name_len')),
    sa.CheckConstraint('hours_per_day > 0 AND hours_per_day <= 24', name=op.f('workspaces_hours_per_day_range')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('workspaces_created_by_fkey'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('workspaces_pkey')),
    sa.UniqueConstraint('slug', name='workspaces_slug_key')
    )
    op.create_table('holidays',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('holiday_date', sa.Date(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('char_length(btrim(name)) BETWEEN 1 AND 80', name=op.f('holidays_name_len')),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('holidays_workspace_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('holidays_pkey')),
    sa.UniqueConstraint('workspace_id', 'holiday_date', name='holidays_one_per_day')
    )
    op.create_table('invitations',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('email', postgresql.CITEXT(), nullable=False),
    sa.Column('role', sa.Text(), nullable=False),
    sa.Column('token_hash', sa.Text(), nullable=False),
    sa.Column('invited_by', sa.UUID(), nullable=True),
    sa.Column('expires_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
    sa.Column('accepted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('accepted_by', sa.UUID(), nullable=True),
    sa.Column('revoked_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('owner', 'member', 'viewer')", name=op.f('invitations_role_valid')),
    sa.CheckConstraint('accepted_at IS NULL OR revoked_at IS NULL', name=op.f('invitations_single_outcome')),
    sa.ForeignKeyConstraint(['accepted_by'], ['users.id'], name=op.f('invitations_accepted_by_fkey'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['invited_by'], ['users.id'], name=op.f('invitations_invited_by_fkey'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('invitations_workspace_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('invitations_pkey')),
    sa.UniqueConstraint('token_hash', name='invitations_token_hash_key')
    )
    op.create_index('invitations_one_open_idx', 'invitations', ['workspace_id', 'email'], unique=True, postgresql_where=sa.text('accepted_at IS NULL AND revoked_at IS NULL'))
    op.create_table('labels',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('color', sa.Text(), server_default='#64748B', nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("color ~ '^#[0-9A-Fa-f]{6}$'", name=op.f('labels_color_hex')),
    sa.CheckConstraint('char_length(btrim(name)) BETWEEN 1 AND 40', name=op.f('labels_name_len')),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('labels_workspace_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('labels_pkey')),
    sa.UniqueConstraint('workspace_id', 'id', name='labels_workspace_id_id_key'),
    sa.UniqueConstraint('workspace_id', 'name', name='labels_name_per_workspace')
    )
    op.create_table('memberships',
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.Text(), nullable=False),
    sa.Column('joined_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('owner', 'member', 'viewer')", name=op.f('memberships_role_valid')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('memberships_user_id_fkey'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('memberships_workspace_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('workspace_id', 'user_id', name='memberships_pkey')
    )
    op.create_index('memberships_user_idx', 'memberships', ['user_id'], unique=False)
    op.create_table('projects',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('key', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('target_end_date', sa.Date(), nullable=False),
    sa.Column('is_template', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('projected_end_date', sa.Date(), nullable=True),
    sa.Column('scheduled_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('next_task_number', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('archived_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("key ~ '^[A-Z][A-Z0-9]{1,9}$'", name=op.f('projects_key_format')),
    sa.CheckConstraint('char_length(btrim(name)) BETWEEN 1 AND 120', name=op.f('projects_name_len')),
    sa.CheckConstraint('next_task_number > 0', name=op.f('projects_next_task_number_positive')),
    sa.CheckConstraint('target_end_date >= start_date', name=op.f('projects_dates_order')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('projects_created_by_fkey'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('projects_workspace_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('projects_pkey')),
    sa.UniqueConstraint('workspace_id', 'id', name='projects_workspace_id_id_key'),
    sa.UniqueConstraint('workspace_id', 'key', name='projects_key_per_workspace')
    )
    op.create_index('projects_active_idx', 'projects', ['workspace_id', 'name'], unique=False, postgresql_where=sa.text('archived_at IS NULL'))
    op.create_table('activity_log',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=True),
    sa.Column('task_id', sa.UUID(), nullable=True),
    sa.Column('actor_id', sa.UUID(), nullable=True),
    sa.Column('entity_type', sa.Text(), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.Column('action', sa.Text(), nullable=False),
    sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('request_id', sa.UUID(), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("action IN ('created', 'updated', 'deleted', 'restored', 'archived', 'unarchived', 'moved', 'rescheduled')", name=op.f('activity_log_action_valid')),
    sa.CheckConstraint("entity_type IN ('workspace', 'membership', 'invitation', 'holiday', 'project', 'sprint', 'task', 'dependency', 'comment', 'attachment', 'time_entry', 'baseline')", name=op.f('activity_log_entity_type_valid')),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('activity_log_actor_id_fkey'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('activity_log_project_id_fkey'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('activity_log_workspace_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('activity_log_pkey'))
    )
    op.create_index('activity_log_entity_idx', 'activity_log', ['entity_type', 'entity_id', sa.literal_column('created_at DESC')], unique=False)
    op.create_index('activity_log_project_idx', 'activity_log', ['project_id', sa.literal_column('created_at DESC')], unique=False)
    op.create_index('activity_log_task_idx', 'activity_log', ['task_id', sa.literal_column('created_at DESC')], unique=False, postgresql_where=sa.text('task_id IS NOT NULL'))
    op.create_index('activity_log_workspace_idx', 'activity_log', ['workspace_id', sa.literal_column('created_at DESC')], unique=False)
    op.create_table('baselines',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('projected_end_date', sa.Date(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('baselines_created_by_fkey'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('baselines_project_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('baselines_pkey')),
    sa.UniqueConstraint('project_id', 'name', name='baselines_name_per_project')
    )
    op.create_table('sprints',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('goal', sa.Text(), nullable=True),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=False),
    sa.Column('status', sa.Text(), server_default='planned', nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('planned', 'active', 'completed')", name=op.f('sprints_status_valid')),
    sa.CheckConstraint('end_date >= start_date', name=op.f('sprints_dates_order')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('sprints_project_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('sprints_pkey')),
    sa.UniqueConstraint('project_id', 'id', name='sprints_project_id_id_key')
    )
    op.create_index('sprints_one_active_idx', 'sprints', ['project_id'], unique=True, postgresql_where=sa.text("status = 'active'"))
    op.create_table('tasks',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('parent_id', sa.UUID(), nullable=True),
    sa.Column('sprint_id', sa.UUID(), nullable=True),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('kind', sa.Text(), server_default='task', nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('owner_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.Text(), server_default='todo', nullable=False),
    sa.Column('priority', sa.Text(), server_default='medium', nullable=False),
    sa.Column('estimate', sa.Numeric(precision=7, scale=2), server_default=sa.text('0'), nullable=False),
    sa.Column('estimate_unit', sa.Text(), server_default='days', nullable=False),
    sa.Column('start_no_earlier_than', sa.Date(), nullable=True),
    sa.Column('position', sa.Text(collation='C'), nullable=False),
    sa.Column('scheduled_start', sa.Date(), nullable=True),
    sa.Column('scheduled_end', sa.Date(), nullable=True),
    sa.Column('slack_days', sa.Integer(), nullable=True),
    sa.Column('is_critical', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('started_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('completed_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(status = 'done') = (completed_at IS NOT NULL)", name=op.f('tasks_done_has_completed_at')),
    sa.CheckConstraint("estimate_unit IN ('hours', 'days')", name=op.f('tasks_estimate_unit_valid')),
    sa.CheckConstraint("kind = 'task' OR estimate = 0", name=op.f('tasks_milestone_no_estimate')),
    sa.CheckConstraint("kind IN ('task', 'milestone')", name=op.f('tasks_kind_valid')),
    sa.CheckConstraint("priority IN ('low', 'medium', 'high', 'urgent')", name=op.f('tasks_priority_valid')),
    sa.CheckConstraint("status IN ('todo', 'in_progress', 'in_review', 'done')", name=op.f('tasks_status_valid')),
    sa.CheckConstraint('char_length(btrim(title)) BETWEEN 1 AND 200', name=op.f('tasks_title_len')),
    sa.CheckConstraint('estimate >= 0 AND estimate <= 9999', name=op.f('tasks_estimate_range')),
    sa.CheckConstraint('number > 0', name=op.f('tasks_number_positive')),
    sa.CheckConstraint('parent_id IS NULL OR parent_id <> id', name=op.f('tasks_not_own_parent')),
    sa.CheckConstraint('scheduled_start IS NULL OR scheduled_end IS NULL OR scheduled_end >= scheduled_start', name=op.f('tasks_schedule_order')),
    sa.CheckConstraint('slack_days IS NULL OR slack_days >= 0', name=op.f('tasks_slack_nonnegative')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('tasks_created_by_fkey'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id', 'parent_id'], ['tasks.project_id', 'tasks.id'], name='tasks_parent_fkey', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id', 'sprint_id'], ['sprints.project_id', 'sprints.id'], name='tasks_sprint_fkey', ondelete='SET NULL (sprint_id)'),
    sa.ForeignKeyConstraint(['workspace_id', 'owner_id'], ['memberships.workspace_id', 'memberships.user_id'], name='tasks_owner_fkey', ondelete='SET NULL (owner_id)'),
    sa.ForeignKeyConstraint(['workspace_id', 'project_id'], ['projects.workspace_id', 'projects.id'], name='tasks_project_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('tasks_pkey')),
    sa.UniqueConstraint('project_id', 'id', name='tasks_project_id_id_key'),
    sa.UniqueConstraint('project_id', 'number', name='tasks_number_per_project'),
    sa.UniqueConstraint('workspace_id', 'id', name='tasks_workspace_id_id_key')
    )
    op.create_index('tasks_board_idx', 'tasks', ['project_id', 'status', 'position'], unique=False, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index('tasks_open_by_end_idx', 'tasks', ['project_id', 'scheduled_end'], unique=False, postgresql_where=sa.text("deleted_at IS NULL AND status <> 'done'"))
    op.create_index('tasks_owner_schedule_idx', 'tasks', ['owner_id', 'scheduled_start', 'scheduled_end'], unique=False, postgresql_where=sa.text("deleted_at IS NULL AND status <> 'done'"))
    op.create_index('tasks_parent_idx', 'tasks', ['parent_id'], unique=False, postgresql_where=sa.text('parent_id IS NOT NULL'))
    op.create_index('tasks_sprint_idx', 'tasks', ['sprint_id'], unique=False, postgresql_where=sa.text('sprint_id IS NOT NULL'))
    op.create_table('attachments',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('task_id', sa.UUID(), nullable=False),
    sa.Column('uploaded_by', sa.UUID(), nullable=True),
    sa.Column('storage_key', sa.Text(), nullable=False),
    sa.Column('file_name', sa.Text(), nullable=False),
    sa.Column('content_type', sa.Text(), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('char_length(file_name) BETWEEN 1 AND 255', name=op.f('attachments_file_name_len')),
    sa.CheckConstraint('size_bytes > 0 AND size_bytes <= 26214400', name=op.f('attachments_size_range')),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], name=op.f('attachments_task_id_fkey'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], name=op.f('attachments_uploaded_by_fkey'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('attachments_pkey')),
    sa.UniqueConstraint('storage_key', name='attachments_storage_key_key')
    )
    op.create_index('attachments_task_idx', 'attachments', ['task_id'], unique=False, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_table('baseline_tasks',
    sa.Column('baseline_id', sa.UUID(), nullable=False),
    sa.Column('task_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('estimate', sa.Numeric(precision=7, scale=2), nullable=False),
    sa.Column('estimate_unit', sa.Text(), nullable=False),
    sa.Column('planned_start', sa.Date(), nullable=True),
    sa.Column('planned_end', sa.Date(), nullable=True),
    sa.Column('is_critical', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['baseline_id'], ['baselines.id'], name=op.f('baseline_tasks_baseline_id_fkey'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], name=op.f('baseline_tasks_task_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('baseline_id', 'task_id', name='baseline_tasks_pkey')
    )
    op.create_table('comments',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('task_id', sa.UUID(), nullable=False),
    sa.Column('author_id', sa.UUID(), nullable=True),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('edited_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('char_length(btrim(body)) BETWEEN 1 AND 10000', name=op.f('comments_body_len')),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], name=op.f('comments_author_id_fkey'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], name=op.f('comments_task_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('comments_pkey'))
    )
    op.create_index('comments_task_idx', 'comments', ['task_id', 'created_at'], unique=False)
    op.create_table('dependencies',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('predecessor_id', sa.UUID(), nullable=False),
    sa.Column('successor_id', sa.UUID(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('predecessor_id <> successor_id', name=op.f('dependencies_not_self')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('dependencies_created_by_fkey'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id', 'predecessor_id'], ['tasks.project_id', 'tasks.id'], name='dependencies_predecessor_fkey', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id', 'successor_id'], ['tasks.project_id', 'tasks.id'], name='dependencies_successor_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('dependencies_pkey')),
    sa.UniqueConstraint('predecessor_id', 'successor_id', name='dependencies_pair_key')
    )
    op.create_index('dependencies_project_idx', 'dependencies', ['project_id'], unique=False)
    op.create_index('dependencies_successor_idx', 'dependencies', ['successor_id'], unique=False)
    op.create_table('task_labels',
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('task_id', sa.UUID(), nullable=False),
    sa.Column('label_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['workspace_id', 'label_id'], ['labels.workspace_id', 'labels.id'], name='task_labels_label_fkey', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id', 'task_id'], ['tasks.workspace_id', 'tasks.id'], name='task_labels_task_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('task_id', 'label_id', name='task_labels_pkey')
    )
    op.create_index('task_labels_label_idx', 'task_labels', ['label_id'], unique=False)
    op.create_table('time_entries',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('task_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('work_date', sa.Date(), nullable=False),
    sa.Column('minutes', sa.Integer(), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('minutes BETWEEN 1 AND 1440', name=op.f('time_entries_minutes_range')),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], name=op.f('time_entries_task_id_fkey'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('time_entries_user_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('time_entries_pkey'))
    )
    op.create_index('time_entries_task_idx', 'time_entries', ['task_id'], unique=False)
    op.create_index('time_entries_user_day_idx', 'time_entries', ['user_id', 'work_date'], unique=False)
    op.create_table('comment_mentions',
    sa.Column('comment_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['comment_id'], ['comments.id'], name=op.f('comment_mentions_comment_id_fkey'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('comment_mentions_user_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('comment_id', 'user_id', name='comment_mentions_pkey')
    )
    op.create_index('comment_mentions_user_idx', 'comment_mentions', ['user_id'], unique=False)
    op.create_table('notifications',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('recipient_id', sa.UUID(), nullable=False),
    sa.Column('actor_id', sa.UUID(), nullable=True),
    sa.Column('type', sa.Text(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=True),
    sa.Column('task_id', sa.UUID(), nullable=True),
    sa.Column('comment_id', sa.UUID(), nullable=True),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('dedupe_key', sa.Text(), nullable=True),
    sa.Column('read_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("type IN ('task_assigned', 'mentioned', 'predecessor_late', 'task_overdue', 'project_late', 'invited', 'role_changed')", name=op.f('notifications_type_valid')),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('notifications_actor_id_fkey'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['comment_id'], ['comments.id'], name=op.f('notifications_comment_id_fkey'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('notifications_project_id_fkey'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], name=op.f('notifications_recipient_id_fkey'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], name=op.f('notifications_task_id_fkey'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('notifications_workspace_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('notifications_pkey'))
    )
    op.create_index('notifications_dedupe_idx', 'notifications', ['recipient_id', 'dedupe_key'], unique=True, postgresql_where=sa.text('dedupe_key IS NOT NULL'))
    op.create_index('notifications_inbox_idx', 'notifications', ['recipient_id', sa.literal_column('created_at DESC')], unique=False)
    op.create_index('notifications_unread_idx', 'notifications', ['recipient_id'], unique=False, postgresql_where=sa.text('read_at IS NULL'))
    # ### end Alembic commands ###
    # Triggers: loop check, one-owner rule, subtask depth, append-only log, updated_at
    for ddl in TRIGGERS:
        op.execute(ddl)


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('notifications_unread_idx', table_name='notifications', postgresql_where=sa.text('read_at IS NULL'))
    op.drop_index('notifications_inbox_idx', table_name='notifications')
    op.drop_index('notifications_dedupe_idx', table_name='notifications', postgresql_where=sa.text('dedupe_key IS NOT NULL'))
    op.drop_table('notifications')
    op.drop_index('comment_mentions_user_idx', table_name='comment_mentions')
    op.drop_table('comment_mentions')
    op.drop_index('time_entries_user_day_idx', table_name='time_entries')
    op.drop_index('time_entries_task_idx', table_name='time_entries')
    op.drop_table('time_entries')
    op.drop_index('task_labels_label_idx', table_name='task_labels')
    op.drop_table('task_labels')
    op.drop_index('dependencies_successor_idx', table_name='dependencies')
    op.drop_index('dependencies_project_idx', table_name='dependencies')
    op.drop_table('dependencies')
    op.drop_index('comments_task_idx', table_name='comments')
    op.drop_table('comments')
    op.drop_table('baseline_tasks')
    op.drop_index('attachments_task_idx', table_name='attachments', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_table('attachments')
    op.drop_index('tasks_sprint_idx', table_name='tasks', postgresql_where=sa.text('sprint_id IS NOT NULL'))
    op.drop_index('tasks_parent_idx', table_name='tasks', postgresql_where=sa.text('parent_id IS NOT NULL'))
    op.drop_index('tasks_owner_schedule_idx', table_name='tasks', postgresql_where=sa.text("deleted_at IS NULL AND status <> 'done'"))
    op.drop_index('tasks_open_by_end_idx', table_name='tasks', postgresql_where=sa.text("deleted_at IS NULL AND status <> 'done'"))
    op.drop_index('tasks_board_idx', table_name='tasks', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_table('tasks')
    op.drop_index('sprints_one_active_idx', table_name='sprints', postgresql_where=sa.text("status = 'active'"))
    op.drop_table('sprints')
    op.drop_table('baselines')
    op.drop_index('activity_log_workspace_idx', table_name='activity_log')
    op.drop_index('activity_log_task_idx', table_name='activity_log', postgresql_where=sa.text('task_id IS NOT NULL'))
    op.drop_index('activity_log_project_idx', table_name='activity_log')
    op.drop_index('activity_log_entity_idx', table_name='activity_log')
    op.drop_table('activity_log')
    op.drop_index('projects_active_idx', table_name='projects', postgresql_where=sa.text('archived_at IS NULL'))
    op.drop_table('projects')
    op.drop_index('memberships_user_idx', table_name='memberships')
    op.drop_table('memberships')
    op.drop_table('labels')
    op.drop_index('invitations_one_open_idx', table_name='invitations', postgresql_where=sa.text('accepted_at IS NULL AND revoked_at IS NULL'))
    op.drop_table('invitations')
    op.drop_table('holidays')
    op.drop_table('workspaces')
    op.drop_index('refresh_tokens_user_idx', table_name='refresh_tokens')
    op.drop_index('refresh_tokens_family_idx', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_index('password_resets_user_idx', table_name='password_resets')
    op.drop_table('password_resets')
    op.drop_table('users')
    # ### end Alembic commands ###
    for name in FUNCTION_NAMES:
        op.execute(f"DROP FUNCTION IF EXISTS {name}()")
