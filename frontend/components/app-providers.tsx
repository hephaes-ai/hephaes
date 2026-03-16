"use client";

import { SWRConfig } from "swr";

import { FeedbackProvider } from "@/components/feedback-provider";
import { ThemeProvider } from "@/components/theme-provider";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem storageKey="hephaes-theme">
      <SWRConfig
        value={{
          keepPreviousData: true,
          revalidateOnFocus: false,
          shouldRetryOnError: false,
        }}
      >
        <FeedbackProvider>{children}</FeedbackProvider>
      </SWRConfig>
    </ThemeProvider>
  );
}
