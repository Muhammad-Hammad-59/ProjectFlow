// Small helper for calling the FastAPI backend.
//
// In the browser, requests go to "/api/..." on the Next.js server, which
// rewrites them to the backend (see next.config.ts). On the server there is
// no origin for a relative URL, so we call the backend directly.

const SERVER_BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Turns any thrown error into one readable line for the UI. Handles FastAPI's
 * two shapes: `detail: "text"` (our HTTPExceptions) and `detail: [{loc, msg}]`
 * (Pydantic validation, 422).
 */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (typeof err.detail === "string") return err.detail;
    if (Array.isArray(err.detail)) {
      const first = err.detail[0] as { loc?: unknown[]; msg?: string } | undefined;
      const field = first?.loc?.at(-1);
      if (first?.msg) return field ? `${String(field)}: ${first.msg}` : first.msg;
    }
  }
  return "Something went wrong. Please try again.";
}

export interface ApiOptions extends Omit<RequestInit, "body"> {
  /** Sent as JSON. */
  body?: unknown;
  /** Sent as "Authorization: Bearer <token>". Defaults to the stored access token. */
  token?: string;
}

// ---- Session -------------------------------------------------------------
// The access token lives only in memory. The refresh token is an httpOnly
// cookie the browser sends to /api/auth/refresh; JS never sees it.

export interface User {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}

let accessToken: string | null = null;
let refreshing: Promise<TokenResponse | null> | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

// How long to wait before retrying when another tab is rotating the cookie.
const REFRESH_RACE_DELAY_MS = 300;

function postRefresh(): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/refresh", { method: "POST", retry: false });
}

/**
 * Swap the refresh cookie for a new access token. Parallel callers in this tab
 * share one request, because each refresh rotates the cookie. A 409 means
 * another tab rotated it a moment ago: wait for its new cookie, then try once
 * more. Resolves null when the session is gone.
 */
export function refreshSession(): Promise<TokenResponse | null> {
  refreshing ??= postRefresh()
    .catch(async (err) => {
      if (!(err instanceof ApiError && err.status === 409)) throw err;
      await new Promise((resolve) => setTimeout(resolve, REFRESH_RACE_DELAY_MS));
      return postRefresh();
    })
    .then((res) => {
      setAccessToken(res.access_token);
      return res;
    })
    .catch(() => {
      setAccessToken(null);
      return null;
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

export function loginUrl(): string {
  if (typeof window === "undefined") return "/login";
  const next = window.location.pathname + window.location.search;
  return `/login?next=${encodeURIComponent(next)}`;
}

function buildUrl(path: string): string {
  const clean = path.startsWith("/") ? path : `/${path}`;
  const base = typeof window === "undefined" ? SERVER_BACKEND_URL : "";
  return `${base}/api${clean}`;
}

/**
 * Call the backend. `path` is relative to /api, e.g. "/projects".
 * On a 401 it refreshes the session once and retries; if that fails it
 * sends the browser to /login.
 */
export async function apiFetch<T = unknown>(
  path: string,
  { body, token, headers, retry = true, ...init }: ApiOptions & { retry?: boolean } = {},
): Promise<T> {
  const finalHeaders = new Headers(headers);
  finalHeaders.set("Accept", "application/json");
  if (body !== undefined) finalHeaders.set("Content-Type", "application/json");
  const bearer = token ?? accessToken;
  if (bearer) finalHeaders.set("Authorization", `Bearer ${bearer}`);

  const res = await fetch(buildUrl(path), {
    credentials: "include",
    ...init,
    headers: finalHeaders,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const isAuthRoute = path.replace(/^\//, "").startsWith("auth/");
  if (res.status === 401 && retry && !token && !isAuthRoute && typeof window !== "undefined") {
    if (await refreshSession()) {
      return apiFetch<T>(path, { body, headers, retry: false, ...init });
    }
    window.location.assign(loginUrl());
  }

  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      const data = await res.json();
      detail = data?.detail ?? data;
    } catch {
      // Body was not JSON; keep the status text.
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

type Opts = Omit<ApiOptions, "method" | "body">;

export const api = {
  get: <T>(path: string, opts?: Opts) =>
    apiFetch<T>(path, { ...opts, method: "GET" }),
  post: <T>(path: string, body?: unknown, opts?: Opts) =>
    apiFetch<T>(path, { ...opts, method: "POST", body }),
  put: <T>(path: string, body?: unknown, opts?: Opts) =>
    apiFetch<T>(path, { ...opts, method: "PUT", body }),
  patch: <T>(path: string, body?: unknown, opts?: Opts) =>
    apiFetch<T>(path, { ...opts, method: "PATCH", body }),
  delete: <T = void>(path: string, opts?: Opts) =>
    apiFetch<T>(path, { ...opts, method: "DELETE" }),
};
