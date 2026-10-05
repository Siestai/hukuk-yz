import type { ReactNode } from "react";

import type { AppNavProps } from "./app-nav";
import { MobileNav } from "./mobile-nav";
import { SideNav } from "./side-nav";

/** Side navigation from `lg` up; below it a sticky top bar with the navigation drawer. */
export function AppShell({ children, ...nav }: AppNavProps & { children: ReactNode }) {
    return (
        <div className="min-h-screen lg:flex">
            <SideNav {...nav} />
            <div className="min-w-0 flex-1">
                <MobileNav user={nav.user} pending={nav.pending} />
                {children}
            </div>
        </div>
    );
}
