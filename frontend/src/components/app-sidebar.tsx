"use client";

// Left navigation of the app shell.

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  CalendarRange,
  FolderKanban,
  LayoutGrid,
  List,
  Settings,
  SquareKanban,
  Users,
  UsersRound,
  type LucideIcon,
} from "lucide-react";

import { initials } from "@/components/ui/avatar-stack";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: "General",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutGrid },
      { href: "/projects", label: "Projects", icon: FolderKanban },
    ],
  },
  {
    // Temporary: these move into per-project tabs once /projects/[id] exists.
    title: "Views",
    items: [
      { href: "/board", label: "Board", icon: SquareKanban },
      { href: "/list", label: "List", icon: List },
      { href: "/timeline", label: "Timeline", icon: CalendarRange },
      { href: "/workload", label: "Workload", icon: Users },
    ],
  },
];

const BOTTOM: NavItem[] = [
  { href: "/team", label: "Team", icon: UsersRound },
  { href: "/settings", label: "Settings", icon: Settings },
];

function NavLink({ href, label, icon: Icon, pathname }: NavItem & { pathname: string }) {
  const active = pathname === href || pathname.startsWith(`${href}/`);
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex h-9 items-center gap-2.5 rounded-lg px-3 text-sm transition-colors",
        active
          ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground shadow-pill"
          : "text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
      )}
    >
      <Icon aria-hidden="true" className="size-4" strokeWidth={active ? 2.25 : 1.75} />
      {label}
    </Link>
  );
}

export function AppSidebar() {
  const pathname = usePathname();
  const { workspace } = useAuth();

  return (
    <aside className="hidden w-60 shrink-0 flex-col gap-6 overflow-y-auto px-4 pt-2 pb-5 md:flex">
      {workspace && (
        <div className="flex items-center gap-2.5 px-1">
          <span
            aria-hidden="true"
            className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-brand-soft-strong text-xs font-semibold text-brand-soft-foreground"
          >
            {initials(workspace.name)}
          </span>
          <span className="flex min-w-0 flex-col">
            <span className="truncate text-sm font-semibold">{workspace.name}</span>
            <span className="text-xs text-muted-foreground capitalize">{workspace.role}</span>
          </span>
        </div>
      )}
      {SECTIONS.map((section) => (
        <nav key={section.title} aria-label={section.title} className="flex flex-col gap-1">
          <h2 className="px-1 pb-1 text-xs font-medium text-foreground">{section.title}</h2>
          {section.items.map((item) => (
            <NavLink key={item.href} {...item} pathname={pathname} />
          ))}
        </nav>
      ))}
      <nav aria-label="Workspace" className="mt-auto flex flex-col gap-1">
        {BOTTOM.map((item) => (
          <NavLink key={item.href} {...item} pathname={pathname} />
        ))}
      </nav>
    </aside>
  );
}
