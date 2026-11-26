import Link from "next/link";

import { AuthVisual } from "@/components/auth-visual";
import { Logo } from "@/components/logo";

/** Split layout from docs/design/auth: form on the right, product visual on the left. */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-1 flex-row-reverse flex-wrap bg-background text-foreground">
      <main className="flex min-h-screen min-w-0 flex-[999_1_420px] flex-col gap-8 px-6 py-8 sm:px-12">
        <Link href="/login" aria-label="ProjectFlow home" className="self-start rounded-lg">
          <Logo />
        </Link>
        <div className="flex grow items-center justify-center">
          <div className="w-full max-w-[380px]">{children}</div>
        </div>
        <footer className="flex flex-wrap justify-between gap-x-6 gap-y-2 text-xs text-muted-foreground">
          <span>© 2026 ProjectFlow</span>
          <nav aria-label="Footer" className="flex gap-5">
            <a href="#" className="hover:text-foreground">Privacy</a>
            <a href="#" className="hover:text-foreground">Help</a>
          </nav>
        </footer>
      </main>
      <div className="flex min-w-0 flex-[1_1_560px] max-[760px]:hidden">
        <AuthVisual />
      </div>
    </div>
  );
}
