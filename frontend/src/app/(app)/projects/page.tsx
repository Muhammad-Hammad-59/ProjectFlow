// Projects list for the current workspace. Placeholder until the projects API exists.

import { EmptyPage } from "@/components/empty-state";

export default function ProjectsPage() {
  return (
    <EmptyPage
      title="Projects"
      description="All projects in your workspace."
      emptyText="No projects yet."
    />
  );
}
