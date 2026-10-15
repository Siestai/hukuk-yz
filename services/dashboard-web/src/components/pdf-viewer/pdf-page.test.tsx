import { describe, expect, it } from "vitest";

import { outputScale } from "./pdf-page";

describe("outputScale", () => {
    it("follows the screen's pixel ratio on a small page", () => {
        expect(outputScale(400, 600, 2)).toBe(2);
        expect(outputScale(400, 600, 1)).toBe(1);
        expect(outputScale(400, 600, 0)).toBe(1);
    });

    it("caps the ratio at 2 on a 3x screen", () => {
        expect(outputScale(400, 600, 3)).toBe(2);
    });

    it("lowers the scale until the canvas area fits the cap", () => {
        const width = 3000;
        const height = 4000;
        const scale = outputScale(width, height, 2);
        expect(scale).toBeLessThan(1);
        expect(Math.floor(width * scale) * Math.floor(height * scale)).toBeLessThanOrEqual(
            8_000_000,
        );
    });
});
