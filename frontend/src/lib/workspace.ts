import { api } from "@/lib/api";

export type Role = "owner" | "member" | "viewer";

/** ISO weekday: 1 = Monday ... 7 = Sunday (same as the API and database). */
export type Weekday = 1 | 2 | 3 | 4 | 5 | 6 | 7;

export const WEEKDAYS: { day: Weekday; short: string; long: string }[] = [
  { day: 1, short: "Mon", long: "Monday" },
  { day: 2, short: "Tue", long: "Tuesday" },
  { day: 3, short: "Wed", long: "Wednesday" },
  { day: 4, short: "Thu", long: "Thursday" },
  { day: 5, short: "Fri", long: "Friday" },
  { day: 6, short: "Sat", long: "Saturday" },
  { day: 7, short: "Sun", long: "Sunday" },
];

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  working_days: Weekday[];
  hours_per_day: number;
  role: Role;
}

export interface Holiday {
  id: string;
  date: string; // YYYY-MM-DD
  name: string;
}

export const workspacesApi = {
  list: () => api.get<Workspace[]>("/workspaces"),
  create: (body: { name: string; slug: string; working_days: Weekday[] }) =>
    api.post<Workspace>("/workspaces", body),
  update: (id: string, body: Partial<Pick<Workspace, "name" | "slug" | "working_days">>) =>
    api.patch<Workspace>(`/workspaces/${id}`, body),
  holidays: (id: string) => api.get<Holiday[]>(`/workspaces/${id}/holidays`),
  addHoliday: (id: string, body: { date: string; name: string }) =>
    api.post<Holiday>(`/workspaces/${id}/holidays`, body),
  deleteHoliday: (id: string, holidayId: string) =>
    api.delete(`/workspaces/${id}/holidays/${holidayId}`),
};

/** "Acme Studio!" → "acme-studio". Matches the server's slug rule. */
export function slugify(name: string): string {
  return name
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48)
    .replace(/-+$/, "");
}

export const SLUG_PATTERN = "[a-z0-9]+(-[a-z0-9]+)*";

const CURRENT_KEY = "pf-workspace";

export function savedWorkspaceId(): string | null {
  try {
    return localStorage.getItem(CURRENT_KEY);
  } catch {
    return null;
  }
}

export function saveWorkspaceId(id: string): void {
  try {
    localStorage.setItem(CURRENT_KEY, id);
  } catch {
    // Storage blocked: falls back to the first workspace next time.
  }
}

/** "2026-12-25" → "Fri 25 Dec 2026", without timezone shifts. */
export function formatDay(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
