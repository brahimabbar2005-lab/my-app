/**
 * Just enough Markdown for AI answers: paragraphs, "- " / "1. " lists,
 * "## " headings and **bold**. Links are never rendered from the answer text:
 * the service puts them in resource/affiliate cards instead.
 */
import { spacing } from '@comemorocco/ui';
import { Text, View } from 'react-native';

import { T } from './ui';

function inline(text: string, keyPrefix: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? (
      <Text key={`${keyPrefix}-${i}`} style={{ fontWeight: '700' }}>
        {part.slice(2, -2)}
      </Text>
    ) : (
      part
    ),
  );
}

export function SimpleMarkdown({ text }: { text: string }) {
  const blocks = text.replace(/\r/g, '').split(/\n{2,}/);
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
                    <T style={{ flex: 1 }}>{inline(line.replace(/^\s*([-*•]|\d+[.)])\s+/, ''), `${b}-${i}`)}</T>
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
              {lines.length > 1 ? <T>{inline(lines.slice(1).join('\n'), `${b}`)}</T> : null}
            </View>
          );
        }
        return <T key={b}>{inline(lines.join('\n'), `${b}`)}</T>;
      })}
    </View>
  );
}
