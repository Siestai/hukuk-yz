"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { cn } from "@hukuk/ui";

const isCurrent = (pathname: string, href: string) =>
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);

export function NavLink({ href, children }: { href: string; children: ReactNode }) {
    const current = isCurrent(usePathname(), href);
    return (
        <Link
            href={href}
            aria-current={current ? "page" : undefined}
            className={cn(
                "flex items-center justify-between rounded-md px-3 py-2 text-sm font-medium",
                current ? "bg-primary-soft text-primary" : "text-ink-2",
            )}
        >
            {children}
        </Link>
    );
}
