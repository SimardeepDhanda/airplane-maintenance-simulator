import type { Metadata } from "next";
import { NotBuilt } from "@/components/feedback/not-built";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Flight schedule" };

export default function FlightsPage() {
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Flight schedule" />
      <NotBuilt phase={3} />
    </div>
  );
}
