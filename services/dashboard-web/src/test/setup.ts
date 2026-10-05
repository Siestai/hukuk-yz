import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(cleanup);

// jsdom has no matchMedia; no query matches and nothing ever changes.
if (typeof window !== "undefined") {
    window.matchMedia ??= (query: string) =>
        ({
            matches: false,
            media: query,
            addEventListener: () => {},
            removeEventListener: () => {},
        }) as unknown as MediaQueryList;
}

// jsdom has no modal dialogs; this mimics the parts the app relies on.
if (typeof HTMLDialogElement !== "undefined") {
    HTMLDialogElement.prototype.showModal ??= function showModal(this: HTMLDialogElement) {
        this.setAttribute("open", "");
    };
    HTMLDialogElement.prototype.close ??= function close(this: HTMLDialogElement) {
        this.removeAttribute("open");
        this.dispatchEvent(new Event("close"));
    };
}
