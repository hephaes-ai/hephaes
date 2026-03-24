"use client";

import { SWRConfig } from "swr";

import { FeedbackProvider } from "@/components/feedback-provider";
import { JobStatusToaster } from "@/components/job-status-toaster";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";

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
        <FeedbackProvider>
          {children}
          <JobStatusToaster />
          <Toaster position="bottom-right" />
        </FeedbackProvider>
      </SWRConfig>
    </ThemeProvider>
  );
}
