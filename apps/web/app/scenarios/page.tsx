import type { Metadata } from "next";
import { Suspense } from "react";
import { ScenariosView } from "@/components/views/scenarios-view";

export const metadata: Metadata = { title: "Scenarios" };

export default function ScenariosPage() {
  return (
    <Suspense>
      <ScenariosView />
    </Suspense>
  );
}
