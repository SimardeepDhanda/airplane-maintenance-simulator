export type NavItem = { href: string; label: string };
export type NavGroup = { label: string; items: NavItem[] };

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Fleet",
    items: [
      { href: "/overview", label: "Overview" },
      { href: "/engines", label: "Engines" },
      { href: "/flights", label: "Flights" },
    ],
  },
  {
    label: "Planning",
    items: [
      { href: "/maintenance", label: "Maintenance" },
      { href: "/scenarios", label: "Scenarios" },
    ],
  },
  {
    label: "Reference",
    items: [{ href: "/methodology", label: "Methodology" }],
  },
];

export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
