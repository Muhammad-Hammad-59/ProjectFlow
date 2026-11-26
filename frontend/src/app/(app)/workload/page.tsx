// Workload view: people x days, red over 8 hours. Placeholder until tasks exist.

import { EmptyPage } from "@/components/empty-state";
import { ProjectViewTabs } from "@/components/project-view-tabs";

export default function WorkloadPage() {
  return (
    <EmptyPage
      title="Workload"
      description="Hours per person per day. Red means over 8 hours."
      emptyText="No assigned work yet."
      tabs={<ProjectViewTabs />}
    />
  );
}
