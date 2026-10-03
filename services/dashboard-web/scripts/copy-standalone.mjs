// `next build` with `output: "standalone"` leaves `.next/static` and `public` out of the standalone
// directory (they are meant for a CDN). Without them the server answers pages but every asset
// 404s, so copy them next to server.js. outputFileTracingRoot is the repo root, hence server.js
// lives under services/dashboard-web/ inside the standalone directory.
import { cpSync, existsSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(fileURLToPath(import.meta.url), "../..");
const server = join(root, ".next/standalone/services/dashboard-web");

if (!existsSync(join(server, "server.js"))) {
    throw new Error(`No standalone server at ${server}: run \`next build\` first.`);
}
cpSync(join(root, ".next/static"), join(server, ".next/static"), { recursive: true });
if (existsSync(join(root, "public"))) {
    cpSync(join(root, "public"), join(server, "public"), { recursive: true });
}
