// Team API client: types for members and invitations, and teamApi calls.

import { api } from "@/lib/api";
import type { Role, Workspace } from "@/lib/workspace";

export interface Member {
  user_id: string;
  full_name: string;
  email: string;
  avatar_url: string | null;
  role: Role;
  joined_at: string;
}

export interface Invitation {
  id: string;
  email: string;
  role: Role;
  invited_by_name: string | null;
  created_at: string;
  expires_at: string;
}

/** Only returned when a link is created or renewed; the server keeps just a hash. */
export interface InvitationCreated extends Invitation {
  token: string;
}

export type InviteStatus = "open" | "expired" | "revoked" | "accepted";

export interface InvitePreview {
  workspace_id: string;
  workspace_name: string;
  inviter_name: string | null;
  email: string;
  role: Role;
  status: InviteStatus;
  expires_at: string;
}

export const ROLES: { role: Role; label: string; short: string; long: string }[] = [
  {
    role: "owner",
    label: "Owner",
    short: "Everything, incl. team and settings",
    long: "As an owner you can manage the team, settings and every project.",
  },
  {
    role: "member",
    label: "Member",
    short: "Plan projects and tasks",
    long: "As a member you can create projects, plan tasks and move work forward.",
  },
  {
    role: "viewer",
    label: "Viewer",
    short: "Read only",
    long: "As a viewer you can see projects, tasks and progress, but not change them.",
  },
];

export const ROLE_LABEL: Record<Role, string> = { owner: "Owner", member: "Member", viewer: "Viewer" };

export const teamApi = {
  members: (ws: string) => api.get<Member[]>(`/workspaces/${ws}/members`),
  changeRole: (ws: string, userId: string, role: Role) =>
    api.patch<Member>(`/workspaces/${ws}/members/${userId}`, { role }),
  remove: (ws: string, userId: string) => api.delete(`/workspaces/${ws}/members/${userId}`),
  invitations: (ws: string) => api.get<Invitation[]>(`/workspaces/${ws}/invitations`),
  invite: (ws: string, email: string, role: Role) =>
    api.post<InvitationCreated>(`/workspaces/${ws}/invitations`, { email, role }),
  renew: (ws: string, id: string) => api.post<InvitationCreated>(`/workspaces/${ws}/invitations/${id}/renew`),
  revoke: (ws: string, id: string) => api.delete(`/workspaces/${ws}/invitations/${id}`),
  preview: (token: string) => api.get<InvitePreview>(`/invitations/${encodeURIComponent(token)}`),
  accept: (token: string) => api.post<Workspace>(`/invitations/${encodeURIComponent(token)}/accept`),
};

export function inviteUrl(token: string): string {
  return `${window.location.origin}/invite/${token}`;
}

/** "in 6 days", "in 3 hours", "expired". */
export function expiresIn(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return "expired";
  const hours = Math.round(ms / 3_600_000);
  if (hours < 24) return `expires in ${Math.max(hours, 1)} hour${hours === 1 ? "" : "s"}`;
  const days = Math.round(hours / 24);
  return `expires in ${days} day${days === 1 ? "" : "s"}`;
}

export function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}
