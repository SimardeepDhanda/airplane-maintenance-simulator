import type { Metadata } from "next";
import { Suspense } from "react";
import { MaintenanceView } from "@/components/views/maintenance-view";

export const metadata: Metadata = { title: "Maintenance planning" };

export default function MaintenancePage() {
  return (
    <Suspense>
      <MaintenanceView />
    </Suspense>
  );
}
