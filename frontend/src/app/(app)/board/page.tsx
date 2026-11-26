// Board view: Kanban columns by status. Placeholder until tasks exist.

import { EmptyPage } from "@/components/empty-state";
import { ProjectViewTabs } from "@/components/project-view-tabs";

export default function BoardPage() {
  return (
    <EmptyPage
      title="Board"
      description="Drag cards between status columns."
      emptyText="No tasks yet."
      tabs={<ProjectViewTabs />}
    />
  );
}
