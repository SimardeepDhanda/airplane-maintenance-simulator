import type { Metadata } from "next";
import { Suspense } from "react";
import { MethodologyView } from "@/components/views/methodology-view";

export const metadata: Metadata = { title: "Methodology" };

export default function Page() {
  return (
    <Suspense>
      <MethodologyView />
    </Suspense>
  );
}
