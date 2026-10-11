// Starts an isolated ARGUS backend for browser tests:
//   * deterministic fixture market data (no network), hash embeddings (no model download)
//   * no language model, no SEC access
//   * a fresh, empty data directory per run (SQLite + Chroma + uploads)
// It serves the static export from backend/app/static, so build first:
//   npm run build && npm run export:backend

import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const backend = resolve(here, '..', '..', 'backend');
const port = process.env.E2E_PORT ?? '8020';

if (!existsSync(join(backend, 'app', 'static', 'index.html'))) {
  console.error('backend/app/static is missing. Run "npm run build && npm run export:backend" first.');
  process.exit(1);
}

const python =
  process.env.E2E_PYTHON ??
  [join(backend, '.venv', 'Scripts', 'python.exe'), join(backend, '.venv', 'bin', 'python')].find((p) => existsSync(p)) ??
  'python';

const dataDir = mkdtempSync(join(tmpdir(), 'argus-e2e-'));
const env = {
  ...process.env,
  ARGUS_ENVIRONMENT: 'test',
  ARGUS_MARKET_DATA_PROVIDER: 'fixture',
  ARGUS_EMBEDDING_PROVIDER: 'hash',
  ARGUS_LLM_PROVIDER: 'none',
  ARGUS_SEC_USER_AGENT: '',
  ARGUS_DATA_DIR: dataDir,
  ARGUS_DATABASE_URL: '',
  ARGUS_CORS_ORIGINS: `["http://127.0.0.1:${port}"]`,
  ARGUS_AUTH_RATE_LIMIT_PER_MINUTE: '200',
  ARGUS_RESEARCH_RATE_LIMIT_PER_MINUTE: '200',
  ARGUS_API_RATE_LIMIT_PER_MINUTE: '5000',
  ARGUS_UPLOAD_RATE_LIMIT_PER_MINUTE: '100',
  ARGUS_LOG_LEVEL: 'WARNING',
};
delete env.ANTHROPIC_API_KEY;
delete env.ARGUS_LLM_API_KEY;

const server = spawn(python, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', port], {
  cwd: backend,
  env,
  stdio: 'inherit',
});

const cleanup = () => {
  server.kill();
  try {
    rmSync(dataDir, { recursive: true, force: true });
  } catch {
    // Windows may hold SQLite/Chroma files briefly; the OS temp dir is cleaned eventually.
  }
};
process.on('SIGINT', () => {
  cleanup();
  process.exit(0);
});
process.on('SIGTERM', () => {
  cleanup();
  process.exit(0);
});
server.on('exit', (code) => {
  cleanup();
  process.exit(code ?? 0);
});
