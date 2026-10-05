import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

const isInteger = (value: string) => /^\d+$/.test(value);

// The custom utilities of styles.css: without them twMerge treats `pb-safe-3` as unknown and keeps
// it next to a `pb-0` a caller passes, so the override would depend on the CSS order.
const twMerge = extendTailwindMerge({
    extend: {
        classGroups: {
            pt: [{ "pt-safe": [isInteger] }],
            pb: [{ "pb-safe": [isInteger] }],
            pl: [{ "pl-safe": [isInteger] }],
            pr: [{ "pr-safe": [isInteger] }],
            px: [{ "px-safe": [isInteger] }],
            w: ["w-inset"],
            h: ["h-viewport"],
            "max-h": ["max-h-inset"],
        },
    },
});

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}
