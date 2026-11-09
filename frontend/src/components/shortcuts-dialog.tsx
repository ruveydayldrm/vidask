"use client";

import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Kbd } from "@/components/ui/misc";
import { useI18n, type TKey } from "@/lib/i18n";

const ROWS: { keys: string[]; label: TKey }[] = [
  { keys: ["/"], label: "shortcuts.focus" },
  { keys: ["Space"], label: "shortcuts.play" },
  { keys: ["J"], label: "shortcuts.back" },
  { keys: ["L"], label: "shortcuts.fwd" },
  { keys: ["?"], label: "shortcuts.help" },
];

export function ShortcutsDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const { t } = useI18n();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={t("shortcuts.title")} className="max-w-sm">
        <ul className="divide-y divide-border">
          {ROWS.map((row) => (
            <li key={row.label} className="flex items-center justify-between py-2.5 text-sm">
              <span className="text-fg-muted">{t(row.label)}</span>
              <span className="flex gap-1">
                {row.keys.map((k) => (
                  <Kbd key={k}>{k}</Kbd>
                ))}
              </span>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
