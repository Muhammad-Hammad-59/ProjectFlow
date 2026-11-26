import * as React from "react"
import { Input as InputPrimitive } from "@base-ui/react/input"
import { cn } from "cn"

/**
 * Text input. Default 36px for in-app forms; `inputSize="lg"` is the 44px
 * auth size. Pass `aria-invalid` for the error border.
 */
function Input({
  className,
  type,
  inputSize = "default",
  ...props
}: React.ComponentProps<"input"> & { inputSize?: "default" | "lg" }) {
  return (
    <InputPrimitive
      type={type}
      data-slot="input"
      className={cn(
        "w-full min-w-0 rounded-lg border border-input bg-subtle px-3 text-sm text-foreground transition-colors outline-none placeholder:text-muted-foreground focus-visible:border-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-60 read-only:border-border read-only:bg-muted aria-invalid:border-2 aria-invalid:border-brand aria-invalid:bg-background",
        inputSize === "lg" ? "h-11 px-3.5" : "h-9",
        className
      )}
      {...props}
    />
  )
}

export { Input }
