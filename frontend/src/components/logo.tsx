import { cn } from "@/lib/utils";

/** The ProjectFlow mark: three stepped bars, like a mini Gantt chart. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 28 28" aria-hidden="true" className={cn("size-7 shrink-0", className)}>
      <rect width="28" height="28" rx="8" className="fill-brand" />
      <rect x="6" y="7" width="10" height="3.5" rx="1.75" className="fill-primary-foreground" />
      <rect x="10" y="12.25" width="12" height="3.5" rx="1.75" className="fill-primary-foreground" />
      <rect x="14" y="17.5" width="8" height="3.5" rx="1.75" className="fill-primary-foreground" />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2.5 text-foreground", className)}>
      <LogoMark />
      <span className="text-[17px] font-semibold tracking-[-0.01em]">ProjectFlow</span>
    </span>
  );
}
