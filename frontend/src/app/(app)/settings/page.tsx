"use client";

// Workspace settings: name, address (slug), working days and holidays. Owners edit; others read.

import { CalendarOff, Lock, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Field, FormAlert } from "@/components/ui/form";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { WorkingDaysPicker } from "@/components/working-days-picker";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorMessage } from "@/lib/api";
import { useAuth, useWorkspace } from "@/lib/auth";
import { cn } from "@/lib/utils";
import {
  SLUG_PATTERN,
  formatDay,
  workspacesApi,
  type Holiday,
  type Weekday,
  type Workspace,
} from "@/lib/workspace";

export default function SettingsPage() {
  const ws = useWorkspace();
  const isOwner = ws.role === "owner";

  return (
    <>
      <PageHeader title="Workspace settings" description="Name, working days and holidays for this workspace." />
      {!isOwner && (
        <div role="note" className="flex items-center gap-2.5 rounded-lg bg-subtle px-3.5 py-3 text-sm text-muted-foreground">
          <Lock aria-hidden="true" className="size-4 shrink-0" />
          Only workspace owners can change these settings. You can see them.
        </div>
      )}
      {/* key: reset the forms when another workspace is selected */}
      <div key={ws.id} className="grid max-w-3xl gap-6">
        <GeneralSection ws={ws} canEdit={isOwner} />
        <HolidaysSection ws={ws} canEdit={isOwner} />
      </div>
    </>
  );
}

function Section({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-5 rounded-2xl bg-card p-6 shadow-card">
      <div className="flex flex-col gap-0.5">
        <h2 className="text-base font-semibold">{title}</h2>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      {children}
    </section>
  );
}

function sameDays(a: Weekday[], b: Weekday[]) {
  return a.length === b.length && a.every((d, i) => d === b[i]);
}

function GeneralSection({ ws, canEdit }: { ws: Workspace; canEdit: boolean }) {
  const { upsertWorkspace } = useAuth();
  const [name, setName] = useState(ws.name);
  const [slug, setSlug] = useState(ws.slug);
  const [days, setDays] = useState<Weekday[]>(ws.working_days);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [pending, setPending] = useState(false);

  const dirty = name.trim() !== ws.name || slug !== ws.slug || !sameDays(days, ws.working_days);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    setPending(true);
    try {
      const updated = await workspacesApi.update(ws.id, { name, slug, working_days: days });
      upsertWorkspace(updated);
      setName(updated.name);
      setSaved(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="contents">
      <Section title="Workspace" description="How your workspace is named and found.">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="ws-name" label="Company or team name">
            <Input id="ws-name" required maxLength={80} disabled={!canEdit} value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field id="ws-slug" label="Workspace address" hint="Lowercase letters, numbers and dashes.">
            <Input
              id="ws-slug"
              required
              maxLength={48}
              pattern={SLUG_PATTERN}
              aria-describedby="ws-slug-hint"
              disabled={!canEdit}
              value={slug}
              onChange={(e) => setSlug(e.target.value.toLowerCase())}
            />
          </Field>
        </div>
      </Section>

      <Section
        title="Working days"
        description="Task dates are counted on these days only. Workload uses them too."
      >
        <WorkingDaysPicker value={days} onChange={setDays} disabled={!canEdit} />
        {error && <FormAlert title={error} />}
        {canEdit && (
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={!dirty || pending}>
              {pending ? "Saving…" : "Save changes"}
            </Button>
            {saved && !dirty && (
              <span role="status" className="text-sm text-success">
                Saved
              </span>
            )}
          </div>
        )}
      </Section>
    </form>
  );
}

function HolidaysSection({ ws, canEdit }: { ws: Workspace; canEdit: boolean }) {
  const [holidays, setHolidays] = useState<Holiday[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [date, setDate] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    workspacesApi
      .holidays(ws.id)
      .then((list) => !cancelled && setHolidays(list))
      .catch((err) => !cancelled && setLoadError(errorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [ws.id]);

  async function handleAdd(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const h = await workspacesApi.addHoliday(ws.id, { date, name });
      setHolidays((list) => [...(list ?? []), h].sort((a, b) => a.date.localeCompare(b.date)));
      setDate("");
      setName("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  async function handleDelete(h: Holiday) {
    setError(null);
    setDeleting(h.id);
    try {
      await workspacesApi.deleteHoliday(ws.id, h.id);
      setHolidays((list) => (list ?? []).filter((x) => x.id !== h.id));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setDeleting(null);
    }
  }

  const today = new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD, local time

  return (
    <Section title="Holidays" description="Days off for everyone. Task dates skip them like weekends.">
      {canEdit && (
        <form onSubmit={handleAdd} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <Field id="hol-date" label="Date">
            <Input id="hol-date" type="date" required value={date} onChange={(e) => setDate(e.target.value)} className="sm:w-44" />
          </Field>
          <div className="grow">
            <Field id="hol-name" label="Name">
              <Input id="hol-name" required maxLength={80} placeholder="Christmas" value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
          </div>
          <Button type="submit" disabled={pending}>
            <Plus />
            {pending ? "Adding…" : "Add holiday"}
          </Button>
        </form>
      )}

      {error && <FormAlert title={error} />}

      {loadError ? (
        <FormAlert title="Couldn't load holidays" body={loadError} />
      ) : holidays === null ? (
        <p role="status" className="text-sm text-muted-foreground">Loading holidays…</p>
      ) : holidays.length === 0 ? (
        <EmptyState text="No holidays yet. Only weekends are skipped." />
      ) : (
        <ul className="flex flex-col divide-y divide-border rounded-xl border border-border">
          {holidays.map((h) => {
            const past = h.date < today;
            return (
              <li key={h.id} className={cn("flex items-center gap-3 px-4 py-2.5", past && "text-muted-foreground")}>
                <CalendarOff aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
                <span className="w-36 shrink-0 text-sm tabular-nums">{formatDay(h.date)}</span>
                <span className="min-w-0 grow truncate text-sm font-medium">{h.name}</span>
                {past && <span className="text-xs">Past</span>}
                {canEdit && (
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Delete ${h.name}`}
                    disabled={deleting === h.id}
                    onClick={() => handleDelete(h)}
                    className="text-muted-foreground hover:text-critical"
                  >
                    <Trash2 />
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
}
