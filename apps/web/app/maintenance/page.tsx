import type { Metadata } from "next";
import { NotBuilt } from "@/components/feedback/not-built";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Maintenance planning" };

export default function MaintenancePage() {
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Maintenance planning" />
      <NotBuilt phase={4} />
    </div>
  );
}
