// @vitest-environment node
import { describe, expect, it } from "vitest";

import { config as dashboardConfig } from "../../dashboard-web/src/proxy";
import { config } from "./proxy";

describe("proxy matcher", () => {
    // Next requires literal config in each entrypoint for static analysis. The dashboard's
    // proxy.test.ts checks the matching behavior; this prevents the two literals drifting.
    it("uses the same static matcher as the dashboard", () => {
        expect(config).toEqual(dashboardConfig);
    });
});
