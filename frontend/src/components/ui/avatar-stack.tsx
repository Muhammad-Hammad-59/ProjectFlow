// Avatars from a name's initials, single or as an overlapping stack.

import { cn } from "cn"

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts.at(-1)![0] : "")).toUpperCase()
}

/* Rotating soft tints so neighbouring avatars are told apart. */
const AVATAR_TONES = [
  "bg-brand-soft-strong text-brand-soft-foreground",
  "bg-info-soft text-info",
  "bg-success-soft text-success",
  "bg-warning-soft text-warning",
  "bg-critical-soft text-critical",
]

function toneFor(name: string): string {
  let hash = 0
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return AVATAR_TONES[hash % AVATAR_TONES.length]
}

export function Avatar({
  name,
  size = "md",
  className,
}: {
  name: string
  size?: "sm" | "md"
  className?: string
}) {
  return (
    <span
      title={name}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full font-semibold ring-2 ring-card",
        size === "sm" ? "size-6 text-[10px]" : "size-8 text-xs",
        toneFor(name),
        className,
      )}
    >
      <span aria-hidden="true">{initials(name)}</span>
      <span className="sr-only">{name}</span>
    </span>
  )
}

/** Overlapping avatars with a "+N" chip, as on board cards and page headers. */
export function AvatarStack({
  names,
  max = 2,
  size = "sm",
}: {
  names: string[]
  max?: number
  size?: "sm" | "md"
}) {
  const shown = names.slice(0, max)
  const rest = names.length - shown.length
  return (
    <span className="flex items-center -space-x-1.5">
      {shown.map((n) => (
        <Avatar key={n} name={n} size={size} />
      ))}
      {rest > 0 && (
        <span
          className={cn(
            "inline-flex items-center justify-center rounded-full bg-muted font-medium text-foreground ring-2 ring-card",
            size === "sm" ? "size-6 text-[10px]" : "size-8 text-xs",
          )}
          aria-label={`and ${rest} more`}
        >
          +{rest}
        </span>
      )}
    </span>
  )
}
