"use client";

// Tabs that switch between a project's views.

import { CalendarRange, List, SquareKanban, Users } from "lucide-react";

import { NavTabs } from "@/components/nav-tabs";

/** Board / List / Timeline / Workload switcher. Will take a project id once /projects/[id] exists. */
export function ProjectViewTabs() {
  return (
    <NavTabs
      label="Project views"
      tabs={[
        { href: "/board", label: "Board", icon: SquareKanban },
        { href: "/list", label: "List", icon: List },
        { href: "/timeline", label: "Timeline", icon: CalendarRange },
        { href: "/workload", label: "Workload", icon: Users },
      ]}
    />
  );
}
