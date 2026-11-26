import { AuthProvider } from "@/lib/auth";

// The user is only known in the browser (token in memory), so AuthProvider
// shows "Loading…" on the server and Next can't validate instant navigation.
export const instant = false;

/** Logged in, but no app shell: the user may not have a workspace yet. */
export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  return <AuthProvider requireWorkspace={false}>{children}</AuthProvider>;
}
