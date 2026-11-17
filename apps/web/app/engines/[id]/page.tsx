import type { Metadata } from "next";
import { Suspense } from "react";
import { EngineDetailView } from "@/components/views/engine-detail-view";

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  return { title: decodeURIComponent((await params).id) };
}

export default async function Page({ params }: Props) {
  const { id } = await params;
  return (
    <Suspense>
      <EngineDetailView id={decodeURIComponent(id)} />
    </Suspense>
  );
}
