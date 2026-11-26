"use client"

// Password input with a show/hide toggle.

import * as React from "react"
import { Eye, EyeOff, Lock } from "lucide-react"

import { InputWithIcon } from "@/components/ui/input-with-icon"

/** Password field with a lock icon and a show/hide toggle. */
function PasswordInput(props: Omit<React.ComponentProps<typeof InputWithIcon>, "icon" | "type" | "action">) {
  const [visible, setVisible] = React.useState(false)
  const Icon = visible ? EyeOff : Eye

  return (
    <InputWithIcon
      icon={Lock}
      type={visible ? "text" : "password"}
      action={
        <button
          type="button"
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          onClick={() => setVisible((v) => !v)}
          className="flex size-11 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground"
        >
          <Icon aria-hidden="true" strokeWidth={1.75} className="size-[18px]" />
        </button>
      }
      {...props}
    />
  )
}

export { PasswordInput }
