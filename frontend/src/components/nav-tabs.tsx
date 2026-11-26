"use client";

// Route-switching tabs (each tab is a link).

import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

export interface NavTab {
  href: string;
  label: string;
  icon: LucideIcon;
}

/** Underlined tabs that switch routes (same look as ui/tabs "line"). */
export function NavTabs({ tabs, label }: { tabs: NavTab[]; label: string }) {
  const pathname = usePathname();
  return (
    <nav aria-label={label} className="flex gap-6 overflow-x-auto">
      {tabs.map(({ href, label: text, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "relative flex h-10 shrink-0 items-center gap-1.5 px-0.5 text-sm font-medium transition-colors",
              "after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:rounded-full after:bg-brand after:opacity-0 after:transition-opacity",
              active ? "text-link after:opacity-100" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon aria-hidden="true" className="size-4" />
            {text}
          </Link>
        );
      })}
    </nav>
  );
}
