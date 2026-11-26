"use client";

// Team page: members and roles for everyone; owners also manage roles and invitations.

import { Mail, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { FormAlert } from "@/components/ui/form";
import { ConfirmDialog, type ConfirmRequest } from "@/components/confirm-dialog";
import { InviteDialog } from "@/components/invite-dialog";
import { PageHeader } from "@/components/page-header";
import { Avatar } from "@/components/ui/avatar-stack";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/api";
import { useAuth, useWorkspace } from "@/lib/auth";
import {
  ROLES,
  ROLE_LABEL,
  expiresIn,
  shortDate,
  teamApi,
  type Invitation,
  type InvitationCreated,
  type Member,
} from "@/lib/team";
import { cn } from "@/lib/utils";
import type { Role } from "@/lib/workspace";

export default function TeamPage() {
  const ws = useWorkspace();
  const { user, upsertWorkspace } = useAuth();
  const isOwner = ws.role === "owner";

  const [members, setMembers] = useState<Member[] | null>(null);
  const [invites, setInvites] = useState<Invitation[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<ConfirmRequest | null>(null);
  const [dialog, setDialog] = useState<{ key: number; open: boolean; link?: InvitationCreated }>({ key: 0, open: false });
  const [rowError, setRowError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [m, i] = await Promise.all([
        teamApi.members(ws.id),
        isOwner ? teamApi.invitations(ws.id) : Promise.resolve([]),
      ]);
      setMembers(m);
      setInvites(i);
    } catch (err) {
      setLoadError(errorMessage(err));
    }
  }, [ws.id, isOwner]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch on mount / workspace change
    load();
  }, [load]);

  function openInvite(link?: InvitationCreated) {
    setDialog((d) => ({ key: d.key + 1, open: true, link }));
  }

  function askRoleChange(m: Member, role: Role) {
    const self = m.user_id === user.id;
    setConfirm({
      title: `Make ${self ? "yourself" : m.full_name} ${ROLE_LABEL[role].toLowerCase()}?`,
      body: self
        ? `You will become a ${ROLE_LABEL[role].toLowerCase()} in ${ws.name}. Another owner would have to change it back.`
        : `${m.full_name} will be a ${ROLE_LABEL[role].toLowerCase()} in ${ws.name}.`,
      confirmLabel: "Change role",
      run: async () => {
        const updated = await teamApi.changeRole(ws.id, m.user_id, role);
        setMembers((list) => list?.map((x) => (x.user_id === m.user_id ? updated : x)) ?? null);
        if (self) upsertWorkspace({ ...ws, role });
      },
    });
  }

  function askRemove(m: Member) {
    setConfirm({
      title: `Remove ${m.full_name}?`,
      body: `Remove ${m.full_name} from ${ws.name}? They lose access right away. Tasks they own become unassigned.`,
      confirmLabel: "Remove",
      destructive: true,
      run: async () => {
        await teamApi.remove(ws.id, m.user_id);
        setMembers((list) => list?.filter((x) => x.user_id !== m.user_id) ?? null);
      },
    });
  }

  function askRevoke(inv: Invitation) {
    setConfirm({
      title: "Revoke invite?",
      body: `The link for ${inv.email} will stop working.`,
      confirmLabel: "Revoke",
      destructive: true,
      run: async () => {
        await teamApi.revoke(ws.id, inv.id);
        setInvites((list) => list.filter((x) => x.id !== inv.id));
      },
    });
  }

  async function renew(inv: Invitation) {
    setRowError(null);
    try {
      const fresh = await teamApi.renew(ws.id, inv.id);
      setInvites((list) => [fresh, ...list.filter((x) => x.id !== inv.id)]);
      openInvite(fresh);
    } catch (err) {
      setRowError(errorMessage(err));
    }
  }

  return (
    <>
      <PageHeader
        title="Team"
        description={`People in ${ws.name} and what they can do.`}
        actions={
          isOwner && (
            <Button onClick={() => openInvite()}>
              <Plus />
              Invite people
            </Button>
          )
        }
      />

      {loadError && <FormAlert title="Couldn't load the team" body={loadError} />}
      {rowError && <FormAlert title={rowError} />}

      <div className="grid max-w-4xl gap-6">
        <Panel title={`Members${members ? ` (${members.length})` : ""}`}>
          {members === null ? (
            <p role="status" className="px-5 py-4 text-muted-foreground">Loading members…</p>
          ) : (
            <ul className="divide-y divide-border">
              {members.map((m) => {
                const self = m.user_id === user.id;
                return (
                  <li key={m.user_id} className="grid grid-cols-[auto_1fr_auto] items-center gap-x-3 gap-y-2 px-5 py-3 md:grid-cols-[auto_1.2fr_1.4fr_9rem_7rem_2.25rem]">
                    <Avatar name={m.full_name} className="ring-0" />
                    <span className="min-w-0">
                      <span className="block truncate font-medium">
                        {m.full_name}
                        {self && <span className="font-normal text-muted-foreground"> · you</span>}
                      </span>
                      <span className="block truncate text-xs text-muted-foreground md:hidden">{m.email}</span>
                    </span>
                    <span className="hidden truncate text-muted-foreground md:block">{m.email}</span>
                    {isOwner ? (
                      <select
                        aria-label={`Role for ${m.full_name}`}
                        value={m.role}
                        onChange={(e) => askRoleChange(m, e.target.value as Role)}
                        className="h-9 rounded-lg border border-input bg-subtle px-2.5 text-sm"
                      >
                        {ROLES.map((r) => (
                          <option key={r.role} value={r.role}>{r.label}</option>
                        ))}
                      </select>
                    ) : (
                      <Badge variant={m.role === "owner" ? "brand" : "outline"} className="justify-self-start">
                        {ROLE_LABEL[m.role]}
                      </Badge>
                    )}
                    <span className="col-span-2 col-start-2 text-xs text-muted-foreground md:col-span-1 md:col-start-auto">
                      Joined {shortDate(m.joined_at)}
                    </span>
                    {isOwner && !self ? (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`Remove ${m.full_name}`}
                        onClick={() => askRemove(m)}
                        className="row-start-1 col-start-3 justify-self-end text-muted-foreground hover:text-critical md:col-start-auto md:row-start-auto"
                      >
                        <Trash2 />
                      </Button>
                    ) : (
                      <span className="hidden md:block" />
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        {isOwner && (
          <Panel title={`Pending invites (${invites.length})`}>
            {invites.length === 0 ? (
              <p className="px-5 py-4 text-muted-foreground">No pending invites.</p>
            ) : (
              <ul className="divide-y divide-border">
                {invites.map((inv) => {
                  const when = expiresIn(inv.expires_at);
                  return (
                    <li key={inv.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3">
                      <Mail aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
                      <span className="min-w-0 grow">
                        <span className="block truncate font-medium">{inv.email}</span>
                        <span className={cn("block text-xs text-muted-foreground", when === "expired" && "text-critical")}>
                          {ROLE_LABEL[inv.role]}
                          {inv.invited_by_name && ` · invited by ${inv.invited_by_name}`} · {when}
                        </span>
                      </span>
                      <span className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => renew(inv)}>New link</Button>
                        <Button variant="ghost" size="sm" onClick={() => askRevoke(inv)} className="text-critical hover:text-critical">
                          Revoke
                        </Button>
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </Panel>
        )}

        <Panel title="What each role can do">
          <dl className="grid gap-x-6 gap-y-2 px-5 py-4 sm:grid-cols-[6rem_1fr]">
            <dt className="font-medium">Owner</dt>
            <dd className="text-muted-foreground">Everything, plus team, roles and workspace settings</dd>
            <dt className="font-medium">Member</dt>
            <dd className="text-muted-foreground">Create and edit projects, tasks and links; comment</dd>
            <dt className="font-medium">Viewer</dt>
            <dd className="text-muted-foreground">Read only</dd>
          </dl>
        </Panel>
      </div>

      <InviteDialog
        key={dialog.key}
        open={dialog.open}
        onOpenChange={(open) => setDialog((d) => ({ ...d, open }))}
        workspaceId={ws.id}
        initialLink={dialog.link}
        onCreated={(inv) => setInvites((list) => [inv, ...list.filter((x) => x.email !== inv.email)])}
      />
      <ConfirmDialog request={confirm} onClose={() => setConfirm(null)} />
    </>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="overflow-hidden rounded-2xl bg-card shadow-card">
      <h2 className="border-b border-border px-5 py-3.5 text-base font-semibold">{title}</h2>
      {children}
    </section>
  );
}
