"use client";

import { MotionConfig } from "framer-motion";
import { ThemeProvider } from "next-themes";

import { TooltipProvider } from "@/components/ui/tooltip";
import { I18nProvider } from "@/lib/i18n";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <I18nProvider>
        <MotionConfig reducedMotion="user">
          <TooltipProvider delayDuration={250}>{children}</TooltipProvider>
        </MotionConfig>
      </I18nProvider>
    </ThemeProvider>
  );
}
