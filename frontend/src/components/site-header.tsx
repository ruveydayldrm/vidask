"use client";

import { Keyboard, Languages, Moon, Settings2, Sun } from "lucide-react";
import Link from "next/link";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { Logo } from "@/components/logo";
import { SettingsDialog } from "@/components/settings-dialog";
import { ShortcutsDialog } from "@/components/shortcuts-dialog";
import { Button } from "@/components/ui/button";
import { SimpleTooltip } from "@/components/ui/tooltip";
import { useI18n } from "@/lib/i18n";
import { isTypingTarget } from "@/lib/utils";

export function SiteHeader() {
  const { t, lang, setLang } = useI18n();
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "?" && !isTypingTarget(e.target)) {
        e.preventDefault();
        setShortcutsOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-bg/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1600px] items-center justify-between px-4 sm:px-6">
        <Link href="/" className="group flex items-center gap-2.5 rounded-lg" aria-label="VidAsk home">
          <Logo className="size-7 transition-transform group-hover:-rotate-6" />
          <span className="text-[15px] font-semibold tracking-tight">VidAsk</span>
        </Link>
        <nav className="flex items-center gap-1" aria-label="Preferences">
          <SimpleTooltip label={t("lang.toggle")}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setLang(lang === "tr" ? "en" : "tr")}
              aria-label={t("lang.toggle")}
              className="font-mono text-xs uppercase"
            >
              <Languages />
              {lang}
            </Button>
          </SimpleTooltip>
          <SimpleTooltip label={t("theme.toggle")}>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t("theme.toggle")}
              onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
            >
              {mounted && resolvedTheme === "dark" ? <Sun /> : <Moon />}
            </Button>
          </SimpleTooltip>
          <SimpleTooltip label={`${t("shortcuts.title")} (?)`}>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t("shortcuts.title")}
              onClick={() => setShortcutsOpen(true)}
              className="hidden sm:inline-flex"
            >
              <Keyboard />
            </Button>
          </SimpleTooltip>
          <SimpleTooltip label={t("settings.title")}>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t("settings.title")}
              onClick={() => setSettingsOpen(true)}
            >
              <Settings2 />
            </Button>
          </SimpleTooltip>
        </nav>
      </div>
      <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
      <ShortcutsDialog open={shortcutsOpen} onOpenChange={setShortcutsOpen} />
    </header>
  );
}
