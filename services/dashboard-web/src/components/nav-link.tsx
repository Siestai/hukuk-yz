"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { cn } from "@hukuk/ui";

const isCurrent = (pathname: string, href: string) =>
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);

export function NavLink({
    href,
    children,
    onNavigate,
}: {
    href: string;
    children: ReactNode;
    onNavigate?: () => void;
}) {
    const current = isCurrent(usePathname(), href);
    return (
        <Link
            href={href}
            aria-current={current ? "page" : undefined}
            onClick={onNavigate}
            className={cn(
                "flex items-center justify-between rounded-md px-3 py-2 text-sm font-medium pointer-coarse:min-h-11",
                current ? "bg-primary-soft text-primary" : "text-ink-2",
            )}
        >
            {children}
        </Link>
    );
}
