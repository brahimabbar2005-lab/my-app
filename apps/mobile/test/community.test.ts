import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { ageParts, POST_KINDS, REPORT_REASONS, validateDraft } from '../src/lib/community-model';

const foundation = readFileSync(join(__dirname, '..', '..', '..', 'supabase', 'migrations', '20260929000001_foundation.sql'), 'utf8');

function checkValues(table: string, column: string): string[] {
  const body = foundation.slice(foundation.indexOf(`create table public.${table} (`));
  const line = body.split('\n').find((l) => l.trim().startsWith(`${column} text`))!;
  const allowed = line.slice(line.indexOf(' in ('));
  return [...allowed.matchAll(/'([a-z_]+)'/g)].map((m) => m[1]!);
}

describe('community model', () => {
  it('report reasons and post kinds match the database constraints', () => {
    expect([...REPORT_REASONS].sort()).toEqual(checkValues('community_reports', 'reason').sort());
    expect([...POST_KINDS].sort()).toEqual(checkValues('community_posts', 'kind').sort());
  });

  it('validates drafts with the table limits', () => {
    const ok = { kind: 'question' as const, destination_id: null, title: 'Fes in July?', body: 'Too hot?' };
    expect(validateDraft(ok)).toBeNull();
    expect(validateDraft({ ...ok, title: '  ab ' })).toBe('title_short');
    expect(validateDraft({ ...ok, title: 'x'.repeat(161) })).toBe('title_long');
    expect(validateDraft({ ...ok, body: '   ' })).toBe('body_empty');
    expect(validateDraft({ ...ok, body: 'x'.repeat(10001) })).toBe('body_long');
  });

  it('formats post age in minutes, hours and days', () => {
    const now = Date.parse('2026-10-01T12:00:00Z');
    expect(ageParts('2026-10-01T11:55:00Z', now)).toEqual({ unit: 'm', value: 5 });
    expect(ageParts('2026-10-01T09:00:00Z', now)).toEqual({ unit: 'h', value: 3 });
    expect(ageParts('2026-09-28T12:00:00Z', now)).toEqual({ unit: 'd', value: 3 });
    expect(ageParts('2026-10-01T12:05:00Z', now)).toEqual({ unit: 'm', value: 0 });
  });
});
