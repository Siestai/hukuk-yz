import { cn } from "@hukuk/ui";
import { describe, expect, it } from "vitest";

describe("cn", () => {
    it("lets a caller override the custom utilities of styles.css", () => {
        expect(cn("pb-safe-3", "pb-0")).toBe("pb-0");
        expect(cn("pb-0", "pb-safe-3")).toBe("pb-safe-3");
        expect(cn("px-safe-4", "pl-2")).toBe("px-safe-4 pl-2");
        expect(cn("pl-2", "px-safe-4")).toBe("px-safe-4");
        expect(cn("p-4", "pt-safe-4")).toBe("p-4 pt-safe-4");
        expect(cn("w-inset", "w-72")).toBe("w-72");
        expect(cn("w-72", "w-inset")).toBe("w-inset");
        expect(cn("h-viewport", "h-11")).toBe("h-11");
        expect(cn("max-h-inset", "max-h-none")).toBe("max-h-none");
    });

    it("keeps utilities that do not conflict", () => {
        expect(cn("pt-safe-2", "pb-safe-2")).toBe("pt-safe-2 pb-safe-2");
        expect(cn("h-viewport", "w-inset")).toBe("h-viewport w-inset");
    });
});
