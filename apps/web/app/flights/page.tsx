import type { Metadata } from "next";
import { Suspense } from "react";
import { FlightsView } from "@/components/views/flights-view";

export const metadata: Metadata = { title: "Flight schedule" };

export default function Page() {
  return (
    <Suspense>
      <FlightsView />
    </Suspense>
  );
}
