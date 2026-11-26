"""Integrity tests for the database schema. They run against the test database
(TEST_DATABASE_URL, set up in conftest.py) after `alembic upgrade head`.
"""
import os
import threading
import uuid

import psycopg
import pytest
from sqlalchemy.engine import make_url

DSN = make_url(os.environ["DATABASE_URL"]).set(drivername="postgresql").render_as_string(hide_password=False)


@pytest.fixture
def db():
    conn = psycopg.connect(DSN)
    yield conn
    conn.rollback()
    conn.close()


def one(conn, sql, *args):
    return conn.execute(sql, args).fetchone()


def make_user(conn, name="Sara"):
    return one(conn, "INSERT INTO users (email, password_hash, full_name) VALUES (%s, 'x', %s) RETURNING id",
               f"{uuid.uuid4().hex[:8]}@acme.test", name)[0]


def make_workspace(conn, owner):
    ws = one(conn, "INSERT INTO workspaces (name, slug, created_by) VALUES ('Acme', %s, %s) RETURNING id",
             "acme-" + uuid.uuid4().hex[:8], owner)[0]
    conn.execute("INSERT INTO memberships (workspace_id, user_id, role) VALUES (%s, %s, 'owner')", (ws, owner))
    return ws


def make_project(conn, ws, key="WEB"):
    return one(conn, """INSERT INTO projects (workspace_id, key, name, start_date, target_end_date)
                        VALUES (%s, %s, 'Website', '2026-11-16', '2026-12-31') RETURNING id""", ws, key)[0]


def make_task(conn, ws, project, title, **cols):
    num = one(conn, "UPDATE projects SET next_task_number = next_task_number + 1 WHERE id = %s "
                    "RETURNING next_task_number - 1", project)[0]
    fields = {"workspace_id": ws, "project_id": project, "number": num, "title": title, "position": f"a{num}"}
    fields.update(cols)
    names = ", ".join(fields)
    marks = ", ".join(["%s"] * len(fields))
    return one(conn, f"INSERT INTO tasks ({names}) VALUES ({marks}) RETURNING id", *fields.values())[0]


def link(conn, project, a, b):
    conn.execute("INSERT INTO dependencies (project_id, predecessor_id, successor_id) VALUES (%s, %s, %s)",
                 (project, a, b))


@pytest.fixture
def world(db):
    owner = make_user(db)
    ws = make_workspace(db, owner)
    project = make_project(db, ws)
    return db, owner, ws, project


# ---------- dependencies ----------

def test_loop_is_rejected_and_named(world):
    db, _, ws, p = world
    design, build, test = (make_task(db, ws, p, t) for t in ("Design", "Build", "Test"))
    link(db, p, design, build)
    link(db, p, build, test)
    with pytest.raises(psycopg.errors.CheckViolation) as err:
        link(db, p, test, design)
    assert err.value.diag.constraint_name == "dependencies_no_cycle"
    path = err.value.diag.message_detail.split(" -> ")
    assert path == [str(test), str(design), str(build), str(test)]


def test_self_link_rejected(world):
    db, _, ws, p = world
    a = make_task(db, ws, p, "A")
    with pytest.raises(psycopg.errors.CheckViolation):
        link(db, p, a, a)


def test_duplicate_link_rejected(world):
    db, _, ws, p = world
    a, b = make_task(db, ws, p, "A"), make_task(db, ws, p, "B")
    link(db, p, a, b)
    with pytest.raises(psycopg.errors.UniqueViolation):
        link(db, p, a, b)


def test_link_across_projects_rejected(world):
    db, _, ws, p = world
    other = make_project(db, ws, "APP")
    a, b = make_task(db, ws, p, "A"), make_task(db, ws, other, "B")
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        link(db, p, a, b)


def test_diamond_is_allowed(world):
    db, _, ws, p = world
    d, b, docs, t = (make_task(db, ws, p, x) for x in ("Design", "Build", "Docs", "Test"))
    for a, z in ((d, b), (d, docs), (b, t), (docs, t)):
        link(db, p, a, z)
    assert one(db, "SELECT count(*) FROM dependencies WHERE project_id = %s", p)[0] == 4


def test_concurrent_opposite_links_cannot_both_commit():
    setup = psycopg.connect(DSN, autocommit=True)
    owner = make_user(setup)
    ws = make_workspace(setup, owner)
    p = make_project(setup, ws, "RACE")
    a, b = make_task(setup, ws, p, "A"), make_task(setup, ws, p, "B")
    results, barrier = [], threading.Barrier(2)

    def worker(x, y):
        conn = psycopg.connect(DSN)
        try:
            barrier.wait()
            link(conn, p, x, y)
            conn.commit()
            results.append("ok")
        except psycopg.errors.CheckViolation:
            conn.rollback()
            results.append("loop")
        finally:
            conn.close()

    threads = [threading.Thread(target=worker, args=pair) for pair in ((a, b), (b, a))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["loop", "ok"]
    setup.execute("DELETE FROM workspaces WHERE id = %s", (ws,))
    setup.execute("DELETE FROM users WHERE id = %s", (owner,))
    setup.close()


# ---------- tasks ----------

def test_owner_must_be_member(world):
    db, _, ws, p = world
    stranger = make_user(db, "Stranger")
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        make_task(db, ws, p, "A", owner_id=stranger)


def test_removing_member_unassigns_tasks(world):
    db, _, ws, p = world
    ali = make_user(db, "Ali")
    db.execute("INSERT INTO memberships (workspace_id, user_id, role) VALUES (%s, %s, 'member')", (ws, ali))
    t = make_task(db, ws, p, "A", owner_id=ali)
    db.execute("DELETE FROM memberships WHERE workspace_id = %s AND user_id = %s", (ws, ali))
    owner_id, workspace_id = one(db, "SELECT owner_id, workspace_id FROM tasks WHERE id = %s", t)
    assert owner_id is None and workspace_id == ws


def test_task_cannot_point_at_other_workspace_project(world):
    db, owner, _ws, p = world
    ws2 = make_workspace(db, owner)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        make_task(db, ws2, p, "A")


def test_subtasks_one_level_only(world):
    db, _, ws, p = world
    parent = make_task(db, ws, p, "Parent")
    child = make_task(db, ws, p, "Child", parent_id=parent)
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        make_task(db, ws, p, "Grandchild", parent_id=child)
    other = make_task(db, ws, p, "Other")
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("UPDATE tasks SET parent_id = %s WHERE id = %s", (other, parent))


def test_done_requires_completed_at(world):
    db, _, ws, p = world
    t = make_task(db, ws, p, "A")
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("UPDATE tasks SET status = 'done' WHERE id = %s", (t,))


def test_milestone_has_no_estimate(world):
    db, _, ws, p = world
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        make_task(db, ws, p, "Launch", kind="milestone", estimate=2)
    make_task(db, ws, p, "Launch", kind="milestone")


def test_task_numbers_are_unique_and_sequential(world):
    db, _, ws, p = world
    ids = [make_task(db, ws, p, f"T{i}") for i in range(3)]
    nums = [one(db, "SELECT number FROM tasks WHERE id = %s", i)[0] for i in ids]
    assert nums == [1, 2, 3]


def test_updated_at_moves(world):
    db, _, ws, p = world
    t = make_task(db, ws, p, "A")
    before = one(db, "SELECT updated_at FROM tasks WHERE id = %s", t)[0]
    db.commit()  # now() is fixed inside one transaction
    db.execute("UPDATE tasks SET title = 'B' WHERE id = %s", (t,))
    after = one(db, "SELECT updated_at FROM tasks WHERE id = %s", t)[0]
    assert after > before
    db.execute("DELETE FROM workspaces WHERE id = %s", (ws,))
    db.commit()


# ---------- workspace ----------

def test_last_owner_cannot_leave_or_be_demoted(world):
    db, owner, ws, _ = world
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("UPDATE memberships SET role = 'member' WHERE workspace_id = %s AND user_id = %s", (ws, owner))


def test_last_owner_can_leave_after_second_owner(world):
    db, owner, ws, _ = world
    other = make_user(db, "Omar")
    db.execute("INSERT INTO memberships (workspace_id, user_id, role) VALUES (%s, %s, 'owner')", (ws, other))
    db.execute("DELETE FROM memberships WHERE workspace_id = %s AND user_id = %s", (ws, owner))


def test_deleting_workspace_cascades(world):
    db, _, ws, p = world
    a, b = make_task(db, ws, p, "A"), make_task(db, ws, p, "B")
    link(db, p, a, b)
    db.execute("DELETE FROM workspaces WHERE id = %s", (ws,))
    assert one(db, "SELECT count(*) FROM tasks WHERE project_id = %s", p)[0] == 0


def test_one_open_invitation_per_email(world):
    db, owner, ws, _ = world
    sql = """INSERT INTO invitations (workspace_id, email, role, token_hash, invited_by, expires_at)
             VALUES (%s, 'ali@acme.test', 'member', %s, %s, now() + interval '7 days')"""
    db.execute(sql, (ws, "t1", owner))
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.execute(sql, (ws, "t2", owner))


def test_bad_working_days_rejected(db):
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("INSERT INTO workspaces (name, slug, working_days) VALUES ('X', 'x-bad', '{1,8}')")


# ---------- audit ----------

def test_activity_log_is_append_only_but_survives_user_delete(world):
    db, _owner, ws, p = world
    actor = make_user(db, "Ali")
    db.execute("""INSERT INTO activity_log (workspace_id, project_id, actor_id, entity_type, entity_id, action, changes)
                  VALUES (%s, %s, %s, 'project', %s, 'created', '{}')""", (ws, p, actor, p))
    db.execute("SAVEPOINT s")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("UPDATE activity_log SET action = 'deleted' WHERE workspace_id = %s", (ws,))
    db.execute("ROLLBACK TO SAVEPOINT s")
    db.execute("DELETE FROM users WHERE id = %s", (actor,))
    assert one(db, "SELECT actor_id FROM activity_log WHERE workspace_id = %s", ws)[0] is None


def test_notification_dedupe(world):
    db, owner, ws, p = world
    sql = """INSERT INTO notifications (workspace_id, recipient_id, type, project_id, dedupe_key)
             VALUES (%s, %s, 'predecessor_late', %s, 'late:x:2026-11-20')"""
    db.execute(sql, (ws, owner, p))
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.execute(sql, (ws, owner, p))
