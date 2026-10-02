/**
 * Just enough Markdown for AI answers: paragraphs, "- " / "1. " lists,
 * "## " headings and **bold**. URLs written in the answer are never rendered
 * as links; the only links are words matched against our own list of
 * comemorocco.com pages (lib/autolink), when `links` is given.
 */
import { spacing } from '@comemorocco/ui';
import { Text, View } from 'react-native';

import { useApp } from '@/lib/app-state';
import { type LinkTerm, linkSegments } from '@/lib/autolink';

import { T } from './ui';

interface Links {
  terms: LinkTerm[];
  used: Set<string>;
  color: string;
  onPress: (url: string) => void;
}

function linked(text: string, key: string, links?: Links) {
  if (!links) return text;
  return linkSegments(text, links.terms, links.used).map((seg, i) =>
    seg.url ? (
      <Text
        key={`${key}-l${i}`}
        accessibilityRole="link"
        onPress={() => links.onPress(seg.url!)}
        style={{ color: links.color, textDecorationLine: 'underline' }}>
        {seg.text}
      </Text>
    ) : (
      seg.text
    ),
  );
}

function inline(text: string, keyPrefix: string, links?: Links) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? (
      <Text key={`${keyPrefix}-${i}`} style={{ fontWeight: '700' }}>
        {linked(part.slice(2, -2), `${keyPrefix}-${i}`, links)}
      </Text>
    ) : (
      linked(part, `${keyPrefix}-${i}`, links)
    ),
  );
}

const LIST_ITEM = /^\s*([-*•]|\d+[.)])\s+/;

/** Models often put a title line straight above a list; give the list its
 * own block so it renders as a list. */
function separateLists(text: string): string {
  const lines = text.split('\n');
  return lines
    .map((line, i) => {
      const prev = lines[i - 1];
      return i > 0 && prev?.trim() && LIST_ITEM.test(line) && !LIST_ITEM.test(prev) ? `\n${line}` : line;
    })
    .join('\n');
}

export function SimpleMarkdown({
  text,
  linkTerms,
  onLink,
}: {
  text: string;
  /** Words to link to comemorocco.com pages; omitted = no links. */
  linkTerms?: LinkTerm[];
  onLink?: (url: string) => void;
}) {
  const { colors } = useApp();
  // One budget per answer: each page is linked at its first mention only.
  const links: Links | undefined =
    linkTerms && onLink ? { terms: linkTerms, used: new Set(), color: colors.secondary, onPress: onLink } : undefined;
  const blocks = separateLists(text.replace(/\r/g, '')).split(/\n{2,}/);
  return (
    <View style={{ gap: spacing.sm }}>
      {blocks.map((block, b) => {
        const lines = block.split('\n').filter((l) => l.trim());
        if (!lines.length) return null;
        if (lines.every((l) => /^\s*([-*•]|\d+[.)])\s+/.test(l))) {
          return (
            <View key={b} style={{ gap: spacing.xs }}>
              {lines.map((line, i) => {
                const marker = line.match(/^\s*(\d+[.)])/)?.[1] ?? '•';
                return (
                  <View key={i} style={{ flexDirection: 'row', gap: spacing.sm }}>
                    <T>{marker}</T>
                    <T style={{ flex: 1 }}>{inline(line.replace(/^\s*([-*•]|\d+[.)])\s+/, ''), `${b}-${i}`, links)}</T>
                  </View>
                );
              })}
            </View>
          );
        }
        if (/^#{1,4}\s/.test(lines[0] ?? '')) {
          return (
            <View key={b} style={{ gap: spacing.xs }}>
              <T variant="bodyStrong">{(lines[0] ?? '').replace(/^#{1,4}\s+/, '')}</T>
              {lines.length > 1 ? <T>{inline(lines.slice(1).join('\n'), `${b}`, links)}</T> : null}
            </View>
          );
        }
        return <T key={b}>{inline(lines.join('\n'), `${b}`, links)}</T>;
      })}
    </View>
  );
}
