// Copy the static export (frontend/out) into backend/app/static so FastAPI can
// serve the UI and API from one origin. The target is replaced, not merged,
// so stale hashed bundles from earlier builds never linger.

import { cpSync, existsSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = join(frontend, 'out');
const target = resolve(frontend, '..', 'backend', 'app', 'static');

if (!existsSync(join(source, 'index.html'))) {
  console.error(`No static export found at ${source}. Run "npm run build" in frontend/ first.`);
  process.exit(1);
}
rmSync(target, { recursive: true, force: true });
cpSync(source, target, { recursive: true });
console.log(`Synced ${source} -> ${target}`);
