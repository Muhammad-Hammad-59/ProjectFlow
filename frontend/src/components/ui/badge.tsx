import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"

const badgeVariants = cva(
  "group/badge inline-flex h-6 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-full border border-transparent px-2.5 py-0.5 text-xs font-medium whitespace-nowrap transition-all focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 [&>svg]:pointer-events-none [&>svg]:size-3!",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground [a]:hover:bg-primary/80",
        secondary:
          "bg-secondary text-secondary-foreground [a]:hover:bg-secondary/80",
        destructive:
          "bg-destructive/10 text-destructive focus-visible:ring-destructive/20 dark:bg-destructive/20 dark:focus-visible:ring-destructive/40 [a]:hover:bg-destructive/20",
        outline:
          "border-border text-foreground [a]:hover:bg-muted [a]:hover:text-muted-foreground",
        ghost:
          "hover:bg-muted hover:text-muted-foreground dark:hover:bg-muted/50",
        link: "text-link underline-offset-4 hover:underline",
        /* Soft orange pill: roles, selected filters */
        brand: "bg-brand-soft text-link",
        /* Outlined pills from the board cards. Pair with PRIORITY_BADGE / STATUS_BADGE. */
        "priority-low": "border-border bg-card text-muted-foreground",
        "priority-medium": "border-brand-soft-strong bg-card text-link",
        "priority-high": "border-warning/35 bg-card text-warning",
        "priority-urgent": "border-critical/30 bg-card text-critical",
        "status-todo": "border-border bg-card text-muted-foreground",
        "status-in_progress": "border-info/30 bg-card text-info",
        "status-in_review": "border-warning/35 bg-card text-warning",
        "status-done": "border-success/30 bg-card text-success",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant = "default",
  render,
  ...props
}: useRender.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return useRender({
    defaultTagName: "span",
    props: mergeProps<"span">(
      {
        className: cn(badgeVariants({ variant }), className),
      },
      props
    ),
    render,
    state: {
      slot: "badge",
      variant,
    },
  })
}

export type Priority = "low" | "medium" | "high" | "urgent"
export type TaskStatus = "todo" | "in_progress" | "in_review" | "done"

export const PRIORITY_LABEL: Record<Priority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  urgent: "Urgent",
}

export const STATUS_LABEL: Record<TaskStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  in_review: "In review",
  done: "Done",
}

function PriorityBadge({ priority, className }: { priority: Priority; className?: string }) {
  return (
    <Badge variant={`priority-${priority}`} className={className}>
      {PRIORITY_LABEL[priority]}
    </Badge>
  )
}

function StatusBadge({ status, className }: { status: TaskStatus; className?: string }) {
  return (
    <Badge variant={`status-${status}`} className={className}>
      {STATUS_LABEL[status]}
    </Badge>
  )
}

export { Badge, badgeVariants, PriorityBadge, StatusBadge }
