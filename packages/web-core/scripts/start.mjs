// `next start` does not work with `output: "standalone"`; the documented way is the generated
// server.js (see scripts/copy-standalone.mjs, run by `pnpm build`). Local default: loopback only.
// Run from the app's directory (`pnpm start` does).
import { spawn } from "node:child_process";
import { basename, join } from "node:path";
import process from "node:process";

const root = process.cwd();
const server = join(root, ".next/standalone/services", basename(root), "server.js");
const env = { PORT: "3000", ...process.env };
// A shell's own HOSTNAME is the machine name, not an address to bind: ignore it.
env.HOSTNAME = process.env.BIND_HOSTNAME ?? "127.0.0.1";

const child = spawn(process.execPath, [server], { env, stdio: "inherit" });
child.on("exit", (code, signal) => process.exit(code ?? (signal ? 1 : 0)));
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
