#!/usr/bin/env node
// Fails if any tracked file contains something that looks like a real secret
// (Master Plan §32, §42). Runs in CI and via `pnpm secrets:scan`.
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

const PATTERNS = [
  ['OpenRouter key', /sk-or-v1-[a-f0-9]{32,}/],
  ['Anthropic key', /sk-ant-[A-Za-z0-9_-]{20,}/],
  ['Cloudflare API token', /\bcfut_[A-Za-z0-9]{20,}/],
  ['Cloudflare account id assignment', /CLOUDFLARE_ACCOUNT_ID\s*=\s*[a-f0-9]{32}/],
  ['Supabase service-role JWT', /eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]*c2VydmljZV9yb2xl[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+/],
  ['Private key', /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/],
  ['AWS access key', /\bAKIA[0-9A-Z]{16}\b/],
  ['Stripe live key', /\bsk_live_[A-Za-z0-9]{20,}/],
];
const SKIP = [/pnpm-lock\.yaml$/, /\.png$/, /\.jpg$/, /\.xlsx$/, /\.ico$/, /^scripts\/scan-secrets\.mjs$/];

const files = execFileSync('git', ['ls-files', '-z'], { encoding: 'utf8' }).split('\0').filter(Boolean);
const findings = [];
for (const file of files) {
  if (SKIP.some((re) => re.test(file))) continue;
  let text;
  try {
    text = readFileSync(file, 'utf8');
  } catch {
    continue;
  }
  for (const [name, re] of PATTERNS) {
    const match = text.match(re);
    if (match) findings.push(`${file}: ${name} (${match[0].slice(0, 12)}…)`);
  }
}
if (findings.length) {
  console.error('Possible secrets in tracked files:\n  ' + findings.join('\n  '));
  process.exit(1);
}
console.log(`secret scan: ${files.length} tracked files clean`);
