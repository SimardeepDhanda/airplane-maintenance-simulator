import type { Metadata } from "next";
import { NotBuilt } from "@/components/feedback/not-built";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Scenarios" };

export default function ScenariosPage() {
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Scenarios" />
      <NotBuilt phase={4} />
    </div>
  );
}
