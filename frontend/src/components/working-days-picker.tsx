"use client";

// Mon-Sun picker for the workspace's working days.

import { Check } from "lucide-react";

import { cn } from "@/lib/utils";
import { WEEKDAYS, type Weekday } from "@/lib/workspace";

/**
 * Mon–Sun toggle buttons (docs/design/auth/Create-Workspace.dc.html).
 * Keeps at least one day selected, as the server requires.
 */
export function WorkingDaysPicker({
  value,
  onChange,
  disabled = false,
  describedBy,
}: {
  value: Weekday[];
  onChange: (days: Weekday[]) => void;
  disabled?: boolean;
  describedBy?: string;
}) {
  function toggle(day: Weekday) {
    const on = value.includes(day);
    if (on && value.length === 1) return; // never zero working days
    onChange(on ? value.filter((d) => d !== day) : [...value, day].sort((a, b) => a - b));
  }

  return (
    <div className="flex flex-wrap gap-2" aria-describedby={describedBy}>
      {WEEKDAYS.map(({ day, short, long }) => {
        const on = value.includes(day);
        const last = on && value.length === 1;
        return (
          <button
            key={day}
            type="button"
            aria-pressed={on}
            aria-label={long}
            title={last ? "At least one working day is needed" : undefined}
            disabled={disabled}
            onClick={() => toggle(day)}
            className={cn(
              "flex h-11 min-w-16 items-center justify-center gap-1.5 rounded-lg border px-3.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-70",
              on
                ? "border-brand bg-brand-soft text-link"
                : "border-input bg-card text-muted-foreground hover:text-foreground",
            )}
          >
            {on && <Check aria-hidden="true" className="size-3.5" strokeWidth={2.5} />}
            {short}
          </button>
        );
      })}
    </div>
  );
}
