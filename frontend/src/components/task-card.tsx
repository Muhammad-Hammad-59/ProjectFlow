// Task card for the board view, with its coloured glow variants.

import { Calendar } from "lucide-react";

import { AvatarStack } from "@/components/ui/avatar-stack";
import { PriorityBadge, StatusBadge, type Priority, type TaskStatus } from "@/components/ui/badge";
import { Tag } from "@/components/ui/tag";
import { cn } from "@/lib/utils";

export type CardGlow = "violet" | "blue" | "peach" | "pink" | "green" | "none";

export const GLOW_CLASS: Record<CardGlow, string> = {
  violet: "card-glow glow-violet",
  blue: "card-glow glow-blue",
  peach: "card-glow glow-peach",
  pink: "card-glow glow-pink",
  green: "card-glow glow-green",
  none: "",
};

export interface TaskCardProps {
  title: string;
  dateLabel?: string;
  description?: string;
  priority?: Priority;
  status?: TaskStatus;
  people?: string[];
  tags?: string[];
  glow?: CardGlow;
  critical?: boolean;
  className?: string;
}

/**
 * Card for a task (board column, My Tasks, dashboard). Reads like the
 * reference: date row, title, optional summary, avatars and tags.
 */
export function TaskCard({
  title,
  dateLabel,
  description,
  priority,
  status,
  people = [],
  tags = [],
  glow = "none",
  critical = false,
  className,
}: TaskCardProps) {
  return (
    <article
      className={cn(
        "flex flex-col gap-3 rounded-2xl bg-card p-4 shadow-card",
        GLOW_CLASS[glow],
        critical && "ring-1 ring-critical/40",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2">
        {dateLabel ? (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Calendar aria-hidden="true" className="size-3.5" />
            {dateLabel}
          </span>
        ) : (
          <span />
        )}
        <span className="flex gap-1.5">
          {status && <StatusBadge status={status} />}
          {priority && <PriorityBadge priority={priority} />}
        </span>
      </div>
      <div className="flex flex-col gap-1">
        <h3 className="text-base leading-snug font-semibold tracking-[-0.01em]">{title}</h3>
        {description && <p className="line-clamp-1 text-xs text-muted-foreground">{description}</p>}
      </div>
      {(people.length > 0 || tags.length > 0) && (
        <div className="flex items-center justify-between gap-2">
          <AvatarStack names={people} />
          <span className="flex flex-wrap justify-end gap-1.5">
            {tags.map((t) => (
              <Tag key={t}>{t}</Tag>
            ))}
          </span>
        </div>
      )}
    </article>
  );
}
