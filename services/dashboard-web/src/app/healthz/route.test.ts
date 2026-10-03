// @vitest-environment node
import { describe, expect, it } from "vitest";

import { GET } from "./route";

describe("healthz", () => {
    it("answers 200 ok without a session or the API", async () => {
        const response = GET();
        expect(response.status).toBe(200);
        expect(await response.text()).toBe("ok");
    });
});
