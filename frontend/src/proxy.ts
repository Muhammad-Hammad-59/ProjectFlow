import { NextResponse, type NextRequest } from "next/server";

// Optimistic check only: a missing refresh cookie means "not logged in", so
// send the user to /login before rendering. The backend still checks every
// request; a stale cookie is caught by AuthProvider's refresh call.
const REFRESH_COOKIE = "pf_refresh";

export function proxy(request: NextRequest) {
  if (request.cookies.has(REFRESH_COOKIE)) return NextResponse.next();

  const { pathname, search } = request.nextUrl;
  const url = new URL("/login", request.url);
  url.searchParams.set("next", pathname + search);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: [
    // Everything except auth pages, invite links (opened before having an account),
    // the API proxy, Next internals and files with an extension.
    "/((?!login|signup|invite|api|_next/static|_next/image|.*\\..*).*)",
  ],
};
