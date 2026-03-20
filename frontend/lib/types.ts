/** Represents one active filter chip in a URL-driven filter bar. */
export interface ActiveFilterChip {
  key: string;
  label: string;
  /** Search param updates to apply when this chip is removed. */
  updates?: Record<string, string | null>;
}

/** Inline notice state used by form and detail surfaces. */
export interface NoticeMessage {
  description?: string;
  title: string;
  tone: "error" | "info" | "success";
}
