// Timeline (Gantt) view: bars, dependency arrows, critical path. Placeholder until tasks exist.

import { EmptyPage } from "@/components/empty-state";
import { ProjectViewTabs } from "@/components/project-view-tabs";

export default function TimelinePage() {
  return (
    <EmptyPage
      title="Timeline"
      description="Gantt bars, dependency arrows and the critical path."
      emptyText="No scheduled tasks yet."
      tabs={<ProjectViewTabs />}
    />
  );
}
