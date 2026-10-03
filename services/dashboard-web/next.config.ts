import { join } from "node:path";

import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const config: NextConfig = {
    output: "standalone",
    outputFileTracingRoot: join(import.meta.dirname, "../.."),
    transpilePackages: ["@hukuk/ui"],
    // The repo's AGENTS.md and .claude/skills are the agent guidance; no generated copies.
    agentRules: false,
};

export default withNextIntl(config);
