import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/600.css";
import "./globals.css";

import type { Metadata } from "next";
import { Suspense, type ReactNode } from "react";
import { SideNav } from "@/components/layout/side-nav";
import { StatusRail } from "@/components/layout/status-rail";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: { default: "AeroFleet", template: "%s · AeroFleet" },
  description: "Engine RUL prediction and maintenance planning simulator for a fictional airline.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="flex h-dvh flex-col">
            <StatusRail />
            <div className="flex min-h-0 flex-1 flex-col md:flex-row">
              <Suspense>
                <SideNav />
              </Suspense>
              <main className="min-w-0 flex-1 overflow-y-auto px-4 py-4 md:px-6">{children}</main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
