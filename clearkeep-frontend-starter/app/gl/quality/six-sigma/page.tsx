// Server redirect alias for: /gl/quality/six-sigma → /quality/six-sigma
// Keeps a single source of truth for the actual page implementation.
import { redirect } from "next/navigation";

export default function Page() {
  redirect("/quality/six-sigma");
}
