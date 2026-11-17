import type { Metadata } from "next";
import { NotBuilt } from "@/components/feedback/not-built";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Engines" };

export default function EnginesPage() {
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Engines" />
      <NotBuilt phase={3} />
    </div>
  );
}
