// Page shell and empty box for screens with nothing to show yet.

import { Inbox } from "lucide-react";

import { PageHeader } from "@/components/page-header";

interface PageShellProps {
  title: string;
  description: string;
  emptyText?: string;
  tabs?: React.ReactNode;
}

/** Empty box shown when a list has no items yet. */
export function EmptyState({ text, children }: { text: string; children?: React.ReactNode }) {
  return (
    <div className="flex min-h-64 flex-col items-center justify-center gap-3 rounded-2xl bg-subtle p-8 text-center">
      <span className="flex size-12 items-center justify-center rounded-2xl bg-brand-soft text-link">
        <Inbox aria-hidden="true" className="size-6" strokeWidth={1.75} />
      </span>
      <p className="text-sm text-muted-foreground">{text}</p>
      {children}
    </div>
  );
}

/** Placeholder page: header plus an empty state. */
export function EmptyPage({ title, description, emptyText = "Nothing here yet.", tabs }: PageShellProps) {
  return (
    <>
      <PageHeader title={title} description={description} tabs={tabs} />
      <EmptyState text={emptyText} />
    </>
  );
}
