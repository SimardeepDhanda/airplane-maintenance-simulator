"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_GROUPS, isActive } from "@/lib/navigation";

export function SideNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Primary"
      className="border-line bg-surface flex shrink-0 gap-4 overflow-x-auto border-b px-3 py-2 md:w-48 md:flex-col md:gap-5 md:overflow-visible md:border-r md:border-b-0 md:px-2 md:py-4"
    >
      {NAV_GROUPS.map((group) => (
        <div
          key={group.label}
          className="flex shrink-0 items-center gap-1 md:flex-col md:items-stretch"
        >
          <span className="text-fg-subtle text-2xs hidden px-2 pb-1 font-medium tracking-wider uppercase md:block">
            {group.label}
          </span>
          {group.items.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-sm px-2 py-1.5 whitespace-nowrap transition-colors md:rounded-none md:border-l-2 ${
                  active
                    ? "text-fg bg-raised md:border-accent"
                    : "text-fg-muted hover:text-fg hover:bg-raised/60 md:border-transparent"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
