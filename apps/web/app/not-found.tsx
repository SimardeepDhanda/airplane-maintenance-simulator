import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-start gap-2 py-8">
      <h1 className="text-base font-semibold">Not found</h1>
      <Link href="/overview" className="text-accent hover:underline">
        Back to overview
      </Link>
    </div>
  );
}
