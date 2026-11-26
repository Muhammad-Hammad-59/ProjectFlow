"use client";

// Top bar of the app shell: logo, theme toggle, your avatar and log out.

import Link from "next/link";
import { Bell, LogOut, Search } from "lucide-react";

import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Avatar } from "@/components/ui/avatar-stack";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

export function TopBar() {
  const { user, logout } = useAuth();

  return (
    <header className="flex h-16 shrink-0 items-center justify-between gap-4 px-5">
      <Link href="/projects" aria-label="ProjectFlow home" className="rounded-lg">
        <Logo />
      </Link>
      <div className="flex items-center gap-2">
        <label className="relative hidden items-center sm:flex">
          <span className="sr-only">Search</span>
          <Search aria-hidden="true" className="pointer-events-none absolute left-3 size-4 text-muted-foreground" />
          <input
            type="search"
            placeholder="Search"
            className="h-9 w-64 rounded-full border border-border bg-subtle pr-3 pl-9 text-sm text-foreground"
          />
        </label>
        <Button variant="outline" size="icon" className="border-border bg-subtle" aria-label="Notifications">
          <Bell />
        </Button>
        <ThemeToggle />
        <Avatar name={user.full_name} className="ring-0" />
        <Button variant="ghost" size="icon" aria-label="Log out" title="Log out" onClick={logout}>
          <LogOut />
        </Button>
      </div>
    </header>
  );
}
