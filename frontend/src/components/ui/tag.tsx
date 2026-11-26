import { cn } from "cn"

/** Small "# Ui" style label chip. */
export function Tag({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center rounded-full border border-border bg-card px-2 text-xs text-muted-foreground",
        className,
      )}
    >
      <span aria-hidden="true" className="mr-0.5">#</span>
      {children}
    </span>
  )
}
