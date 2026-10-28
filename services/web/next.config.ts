import { join } from "node:path";

import { staticSecurityHeaders } from "@hukuk/web-core/lib/security-headers";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const config: NextConfig = {
    output: "standalone",
    outputFileTracingRoot: join(import.meta.dirname, "../.."),
    transpilePackages: ["@hukuk/ui", "@hukuk/web-core"],
    // The repo's AGENTS.md and .claude/skills are the agent guidance; no generated copies.
    agentRules: false,
    headers: async () => [{ source: "/:path*", headers: staticSecurityHeaders() }],
};

export default withNextIntl(config);
