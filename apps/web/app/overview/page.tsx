import type { Metadata } from "next";
import { NotBuilt } from "@/components/feedback/not-built";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Fleet health" };

export default function OverviewPage() {
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Fleet health" />
      <NotBuilt phase={3} />
    </div>
  );
}
