import type { Metadata } from "next";
import { Suspense } from "react";
import { EnginesView } from "@/components/views/engines-view";

export const metadata: Metadata = { title: "Engines" };

export default function Page() {
  return (
    <Suspense>
      <EnginesView />
    </Suspense>
  );
}
