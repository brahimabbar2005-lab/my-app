/** Pieces shared by the community feed, post and compose screens. */
import { spacing } from '@comemorocco/ui';
import { useState } from 'react';
import { Modal, Pressable, TextInput, View } from 'react-native';

import { Button, Card, Chip, T } from '@/components/ui';
import { catalog, destinationName } from '@/data/catalog';
import { useApp } from '@/lib/app-state';
import { ageParts, REPORT_REASONS, type ReportReason } from '@/lib/community';

export function PostAge({ iso }: { iso: string }) {
  const { t } = useApp();
  const { unit, value } = ageParts(iso);
  return <>{t(unit === 'm' ? 'community.ageM' : unit === 'h' ? 'community.ageH' : 'community.ageD', { n: value })}</>;
}

export function DestinationChips({ selected, onSelect }: { selected: string | null; onSelect: (id: string) => void }) {
  const { locale } = useApp();
  return (
    <>
      {catalog.destinations.map((d) => (
        <Chip key={d.id} label={destinationName(d, locale)} selected={selected === d.id} onPress={() => onSelect(d.id)} />
      ))}
    </>
  );
}

/** Reason picker for reports: the reason is required, details are optional. */
export function ReportSheet({
  visible,
  onClose,
  onSubmit,
}: {
  visible: boolean;
  onClose: () => void;
  onSubmit: (reason: ReportReason, details: string) => Promise<void>;
}) {
  const { t, colors } = useApp();
  const [reason, setReason] = useState<ReportReason | null>(null);
  const [details, setDetails] = useState('');
  const [busy, setBusy] = useState(false);

  const close = () => {
    setReason(null);
    setDetails('');
    onClose();
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={close}>
      <View style={{ flex: 1, justifyContent: 'flex-end' }}>
        {/* The backdrop is a sibling of the sheet, not its parent: nested
            pressables are invalid on web. */}
        <Pressable
          onPress={close}
          accessibilityRole="button"
          accessibilityLabel={t('common.cancel')}
          style={{ position: 'absolute', top: 0, bottom: 0, left: 0, right: 0, backgroundColor: 'rgba(0,0,0,0.4)' }}
        />
        <View style={{ padding: spacing.md }}>
          <Card>
            <T variant="heading">{t('community.reportTitle')}</T>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm }}>
              {REPORT_REASONS.map((r) => (
                <Chip key={r} label={t(`community.reason_${r}`)} selected={reason === r} onPress={() => setReason(r)} />
              ))}
            </View>
            <TextInput
              value={details}
              onChangeText={setDetails}
              placeholder={t('community.reportDetails')}
              placeholderTextColor={colors.textMuted}
              multiline
              maxLength={2000}
              accessibilityLabel={t('community.reportDetails')}
              style={{
                borderWidth: 1,
                borderColor: colors.border,
                borderRadius: 12,
                padding: spacing.md,
                minHeight: 72,
                color: colors.text,
                textAlignVertical: 'top',
              }}
            />
            <Button
              label={t('community.sendReport')}
              icon="flag-outline"
              kind="danger"
              disabled={!reason}
              loading={busy}
              onPress={async () => {
                if (!reason) return;
                setBusy(true);
                await onSubmit(reason, details);
                setBusy(false);
                close();
              }}
            />
            <Button label={t('common.cancel')} kind="ghost" onPress={close} />
          </Card>
        </View>
      </View>
    </Modal>
  );
}
