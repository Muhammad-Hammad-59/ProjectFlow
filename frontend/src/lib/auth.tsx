"use client";

// Session state for the logged-in app: who you are, your workspaces, and which
// one is open. Pages read it with useAuth() / useWorkspace().

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, loginUrl, refreshSession, setAccessToken, type User } from "@/lib/api";
import { saveWorkspaceId, savedWorkspaceId, workspacesApi, type Workspace } from "@/lib/workspace";

interface AuthContextValue {
  user: User;
  logout: () => Promise<void>;
  /** All workspaces the user belongs to. */
  workspaces: Workspace[];
  /** The one the app is showing. Null only on /onboarding before the first is made. */
  workspace: Workspace | null;
  selectWorkspace: (id: string) => void;
  /** Replace one workspace in the list (after a save) or add a new one. */
  upsertWorkspace: (ws: Workspace) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Wraps the logged-in part of the app. On mount it trades the refresh cookie
 * for an access token (so a page reload keeps you logged in) and sends you to
 * /login if that fails. It then loads your workspaces; with
 * `requireWorkspace`, a user without one is sent to /onboarding.
 */
export function AuthProvider({
  children,
  requireWorkspace = true,
}: {
  children: React.ReactNode;
  requireWorkspace?: boolean;
}) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[] | null>(null);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await refreshSession();
      if (cancelled) return;
      if (!res) {
        router.replace(loginUrl());
        return;
      }
      let list: Workspace[];
      try {
        list = await workspacesApi.list();
      } catch {
        if (!cancelled) setLoadFailed(true);
        return;
      }
      if (cancelled) return;
      setUser(res.user);
      setWorkspaces(list);
      const saved = savedWorkspaceId();
      setCurrentId(list.find((w) => w.id === saved)?.id ?? list[0]?.id ?? null);
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  const mustOnboard = requireWorkspace && workspaces !== null && workspaces.length === 0;
  useEffect(() => {
    if (mustOnboard) router.replace("/onboarding");
  }, [mustOnboard, router]);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setAccessToken(null);
      setUser(null);
      router.replace("/login");
    }
  }, [router]);

  const selectWorkspace = useCallback((id: string) => {
    saveWorkspaceId(id);
    setCurrentId(id);
  }, []);

  const upsertWorkspace = useCallback((ws: Workspace) => {
    setWorkspaces((list) => {
      const all = list ?? [];
      return all.some((w) => w.id === ws.id) ? all.map((w) => (w.id === ws.id ? ws : w)) : [...all, ws];
    });
  }, []);

  const value = useMemo<AuthContextValue | null>(() => {
    if (!user || !workspaces) return null;
    return {
      user,
      logout,
      workspaces,
      workspace: workspaces.find((w) => w.id === currentId) ?? null,
      selectWorkspace,
      upsertWorkspace,
    };
  }, [user, workspaces, currentId, logout, selectWorkspace, upsertWorkspace]);

  if (!value || mustOnboard) {
    return (
      <div role="status" className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
        {loadFailed ? "Couldn't load your workspaces. Check your connection and reload the page." : "Loading…"}
      </div>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** The current workspace, for pages inside the app shell (always set there). */
export function useWorkspace(): Workspace {
  const { workspace } = useAuth();
  if (!workspace) throw new Error("useWorkspace needs a workspace; is this page outside the app shell?");
  return workspace;
}

const AFTER_LOGIN = "/projects";

/**
 * Only allow same-site paths as a post-login destination, so `?next=` can't send
 * people to another site. Browsers read "\" like "/", so "/\evil.com" means
 * "//evil.com": reject backslashes too, then confirm the origin by parsing.
 */
export function safeNext(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.includes("\\")) return AFTER_LOGIN;
  if (typeof window === "undefined") return next;
  try {
    const url = new URL(next, window.location.origin);
    return url.origin === window.location.origin ? url.pathname + url.search + url.hash : AFTER_LOGIN;
  } catch {
    return AFTER_LOGIN;
  }
}
