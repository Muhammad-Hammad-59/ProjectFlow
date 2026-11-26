import { AppSidebar } from "@/components/app-sidebar";
import { TopBar } from "@/components/top-bar";
import { AuthProvider } from "@/lib/auth";

// The user is only known in the browser (token in memory), so AuthProvider
// shows "Loading…" on the server and Next can't validate instant navigation.
export const instant = false;

/**
 * App shell: warm canvas with the top bar and sidebar sitting on it, and the
 * page in a white panel with a rounded top-left corner.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <div className="flex h-screen flex-col bg-canvas">
        <TopBar />
        <div className="flex min-h-0 flex-1">
          <AppSidebar />
          <main className="min-w-0 flex-1 overflow-auto rounded-tl-[20px] bg-background">
            <div className="flex flex-col gap-6 px-6 py-5">{children}</div>
          </main>
        </div>
      </div>
    </AuthProvider>
  );
}
