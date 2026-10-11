import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ScanRefresh } from "./scan-refresh";

const refresh = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

beforeEach(() => {
    vi.useFakeTimers();
    refresh.mockClear();
});
afterEach(() => vi.useRealTimers());

describe("ScanRefresh", () => {
    it("asks for fresh data every 5 seconds while a scan is active, for 2 minutes at most", () => {
        render(<ScanRefresh active />);
        vi.advanceTimersByTime(4_999);
        expect(refresh).not.toHaveBeenCalled();
        vi.advanceTimersByTime(1);
        expect(refresh).toHaveBeenCalledTimes(1);
        vi.advanceTimersByTime(10 * 60_000);
        expect(refresh).toHaveBeenCalledTimes(23);
    });

    it("skips the tick while the tab is hidden", () => {
        const hidden = vi.spyOn(document, "hidden", "get").mockReturnValue(true);
        render(<ScanRefresh active />);
        vi.advanceTimersByTime(15_000);
        expect(refresh).not.toHaveBeenCalled();
        hidden.mockReturnValue(false);
        vi.advanceTimersByTime(5_000);
        expect(refresh).toHaveBeenCalledTimes(1);
        hidden.mockRestore();
    });

    it("does nothing when no scan is active, and stops once it is over", () => {
        const { rerender } = render(<ScanRefresh active />);
        vi.advanceTimersByTime(5_000);
        rerender(<ScanRefresh active={false} />);
        vi.advanceTimersByTime(60_000);
        expect(refresh).toHaveBeenCalledTimes(1);
        refresh.mockClear();
        const idle = render(<ScanRefresh active={false} />);
        vi.advanceTimersByTime(60_000);
        expect(refresh).not.toHaveBeenCalled();
        idle.unmount();
    });
});
