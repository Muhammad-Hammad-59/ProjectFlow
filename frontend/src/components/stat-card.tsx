// KPI tile for the dashboard.

import type { LucideIcon } from "lucide-react";
import { TrendingDown, TrendingUp } from "lucide-react";

import { GLOW_CLASS, type CardGlow } from "@/components/task-card";
import { cn } from "@/lib/utils";

/** Dashboard KPI tile: icon + label, big number, optional trend line. */
export function StatCard({
  icon: Icon,
  label,
  value,
  trend,
  glow = "none",
}: {
  icon: LucideIcon;
  label: string;
  value: string | number;
  trend?: { direction: "up" | "down"; text: string; good?: boolean };
  glow?: CardGlow;
}) {
  const TrendIcon = trend?.direction === "down" ? TrendingDown : TrendingUp;
  const good = trend?.good ?? trend?.direction === "up";
  return (
    <div className={cn("flex flex-col gap-3 rounded-2xl bg-card p-4 shadow-card", GLOW_CLASS[glow])}>
      <span className="flex items-center gap-2 text-sm text-muted-foreground">
        <Icon aria-hidden="true" className="size-4" />
        {label}
      </span>
      <span className="text-3xl font-semibold tracking-[-0.02em]">{value}</span>
      {trend && (
        <span className={cn("flex items-center gap-1 text-xs", good ? "text-success" : "text-critical")}>
          <TrendIcon aria-hidden="true" className="size-3.5" />
          {trend.text}
        </span>
      )}
    </div>
  );
}
