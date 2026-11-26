// Input with a leading icon and an optional trailing action.

import * as React from "react"
import type { LucideIcon } from "lucide-react"
import { cn } from "cn"

import { Input } from "@/components/ui/input"

/** 44px input with a leading icon and an optional trailing action (e.g. show password). */
function InputWithIcon({
  icon: Icon,
  action,
  className,
  ...props
}: React.ComponentProps<typeof Input> & { icon: LucideIcon; action?: React.ReactNode }) {
  return (
    <div className="relative flex items-center">
      <Icon
        aria-hidden="true"
        strokeWidth={1.75}
        className="pointer-events-none absolute left-3.5 size-[18px] text-muted-foreground"
      />
      <Input inputSize="lg" className={cn("pl-[42px]", action && "pr-12", className)} {...props} />
      {action && <div className="absolute inset-y-0 right-0 flex">{action}</div>}
    </div>
  )
}

export { InputWithIcon }
