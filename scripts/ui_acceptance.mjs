import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname;
const PORT = 18124;
const BASE = `http://127.0.0.1:${PORT}`;
const DB_DIR = mkdtempSync(join(tmpdir(), 'xray-ui-'));
const DB_PATH = join(DB_DIR, 'ui.db');
const ARTIFACT_DIR = join(ROOT, 'artifacts', 'ui');
mkdirSync(ARTIFACT_DIR, { recursive: true });

function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

async function api(path, method = 'GET', body = null, token = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(BASE + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  const parsed = response.headers.get('content-type')?.includes('json') ? JSON.parse(text) : text;
  if (!response.ok) {
    throw new Error(`API ${method} ${path} failed (${response.status}): ${text}`);
  }
  return parsed;
}

async function startServer() {
  const env = {
    ...process.env,
    DB_PATH,
    PORT: String(PORT),
    ADMIN_TOKEN: 'ui-admin-token-12345678901234567890',
    REVIEWER_TOKENS: 'reviewer-a:ui-review-token-a,reviewer-b:ui-review-token-b',
    SCANNER_TOKENS: 'scanner-a:ui-scan-token-a',
    APP_ENV: 'test',
    TOKEN_PEPPER: 'ui-token-pepper-1234567890123456789012',
    AUDIT_HMAC_KEY: 'ui-audit-key-123456789012345678901234',
    BACKUP_HMAC_KEY: 'ui-backup-key-1234567890123456789012',
    WRITE_RATE_LIMIT: '1000',
    PUBLIC_READ_RATE_LIMIT: '1000',
    AUTH_READ_RATE_LIMIT: '1000',
    EXPENSIVE_WRITE_RATE_LIMIT: '1000',
  };
  const child = spawn('python3', ['app/server.py'], {
    cwd: ROOT,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let stderr = '';
  child.stderr.on('data', chunk => { stderr += chunk.toString(); });
  for (let i = 0; i < 80; i += 1) {
    try {
      const response = await fetch(BASE + '/ready');
      if (response.ok) return { child, stderrRef: () => stderr };
    } catch {}
    await sleep(100);
  }
  throw new Error(stderr || 'server failed to become ready');
}

async function seedData() {
  const admin = 'ui-admin-token-12345678901234567890';
  const project = await api('/api/projects', 'POST', {
    title: 'UI acceptance fixture',
    authority: 'Synthetic Authority',
    location: 'Test Location',
    summary: 'Browser acceptance evidence flow',
    synthetic: true,
  }, admin);
  const source = await api(`/api/projects/${project.id}/sources`, 'POST', {
    publisher: 'Synthetic Publisher',
    url: 'https://example.invalid/ui',
    source_class: 'official',
    retrieved_at: '2026-07-14T00:00:00Z',
    sha256: 'a'.repeat(64),
    passage: 'Synthetic browser anchor',
  }, admin);
  const document = await api(`/api/projects/${project.id}/documents`, 'POST', {
    source_id: source.id,
    filename: 'fixture.pdf',
    media_type: 'application/pdf',
    size_bytes: 128,
    sha256: 'b'.repeat(64),
  }, admin);
  await api(`/api/projects/${project.id}/documents/${document.id}/scan`, 'POST', { result: 'clean' }, 'ui-scan-token-a');
  const claim = await api(`/api/projects/${project.id}/claims`, 'POST', {
    claim_type: 'official_claim',
    text: 'Synthetic browser-reviewed claim',
    source_id: source.id,
    passage: 'Synthetic browser anchor',
  }, admin);
  await api(`/api/projects/${project.id}/claims/${claim.id}/reviews`, 'POST', { decision: 'approve' }, 'ui-review-token-a');
  await api(`/api/projects/${project.id}/claims/${claim.id}/reviews`, 'POST', { decision: 'approve' }, 'ui-review-token-b');
  await api(`/api/projects/${project.id}/claims/${claim.id}/publish`, 'POST', {}, admin);
  await api(`/api/projects/${project.id}/publish`, 'POST', {}, admin);
  return project.id;
}

async function run() {
  const { child, stderrRef } = await startServer();
  try {
    const projectId = await seedData();
    const launchOpts = { headless: true };
    if (process.env.CHROMIUM_PATH) {
      launchOpts.executablePath = process.env.CHROMIUM_PATH;
    }
    const browser = await chromium.launch(launchOpts);
    const context = await browser.newContext();
    await context.tracing.start({ screenshots: true, snapshots: true });
    const page = await context.newPage();
    try {
      await page.goto(BASE, { waitUntil: 'networkidle' });
      await page.getByText('Project X-Ray India').waitFor();
      await page.getByRole('button', { name: 'Refresh' }).click();
      await page.getByRole('button', { name: 'View dossier' }).click();
      await page.getByText('Important:').waitFor();
      await page.getByText('human review').waitFor();
      await page.getByRole('link', { name: 'Evidence report' }).waitFor();
      await page.getByRole('link', { name: 'Draft RTI' }).waitFor();
      const capsuleLink = page.getByRole('link', { name: 'Evidence capsule' });
      await capsuleLink.waitFor();
      const href = await capsuleLink.getAttribute('href');
      if (href !== `/api/projects/${projectId}/capsule`) {
        throw new Error(`unexpected capsule href: ${href}`);
      }
      await page.screenshot({ path: join(ARTIFACT_DIR, 'ui-acceptance.png'), fullPage: true });
      await context.tracing.stop({ path: join(ARTIFACT_DIR, 'ui-acceptance-trace.zip') });
    } catch (error) {
      await page.screenshot({ path: join(ARTIFACT_DIR, 'ui-acceptance-failure.png'), fullPage: true });
      await context.tracing.stop({ path: join(ARTIFACT_DIR, 'ui-acceptance-trace-failure.zip') });
      throw error;
    } finally {
      await browser.close();
    }
    writeFileSync(join(ARTIFACT_DIR, 'ui-acceptance.json'), JSON.stringify({ status: 'ok', project_id: projectId }));
    console.log(JSON.stringify({ status: 'ok', project_id: projectId }));
  } finally {
    child.kill('SIGTERM');
    await sleep(250);
    if (!child.killed) child.kill('SIGKILL');
    const stderr = stderrRef();
    if (stderr) process.stderr.write(stderr);
  }
}

run().catch(error => {
  console.error(error);
  process.exit(1);
});
