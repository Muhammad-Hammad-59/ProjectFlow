// The root URL just sends people to their projects.

import { redirect } from "next/navigation";

export default function Home() {
  redirect("/projects");
}
