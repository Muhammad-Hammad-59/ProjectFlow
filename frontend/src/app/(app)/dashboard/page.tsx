// Project dashboard: % done, overdue tasks, tasks per person. Placeholder for now.

import { EmptyPage } from "@/components/empty-state";

export default function DashboardPage() {
  return (
    <EmptyPage
      title="Dashboard"
      description="Progress, overdue tasks and tasks per person."
      emptyText="No project selected."
    />
  );
}
