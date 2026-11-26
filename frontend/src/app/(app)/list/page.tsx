// List view: sortable, filterable task table. Placeholder until tasks exist.

import { EmptyPage } from "@/components/empty-state";
import { ProjectViewTabs } from "@/components/project-view-tabs";

export default function ListPage() {
  return (
    <EmptyPage
      title="List"
      description="A sortable, filterable table of tasks."
      emptyText="No tasks yet."
      tabs={<ProjectViewTabs />}
    />
  );
}
