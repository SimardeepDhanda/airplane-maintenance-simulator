import type { Metadata } from "next";
import { Suspense } from "react";
import { OverviewView } from "@/components/views/overview-view";

export const metadata: Metadata = { title: "Fleet health" };

export default function Page() {
  return (
    <Suspense>
      <OverviewView />
    </Suspense>
  );
}
