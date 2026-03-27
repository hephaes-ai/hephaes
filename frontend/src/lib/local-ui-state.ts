import * as React from "react";

function readStoredValue<T>(storageKey: string, fallbackValue: T): T {
  if (typeof window === "undefined") {
    return fallbackValue;
  }

  try {
    const rawValue = window.localStorage.getItem(storageKey);
    if (!rawValue) {
      return fallbackValue;
    }

    return JSON.parse(rawValue) as T;
  } catch {
    return fallbackValue;
  }
}

export function usePersistentUiState<T>(storageKey: string, fallbackValue: T) {
  const [value, setValue] = React.useState<T>(() => readStoredValue(storageKey, fallbackValue));

  React.useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    try {
      window.localStorage.setItem(storageKey, JSON.stringify(value));
    } catch {
      // Ignore storage failures to keep the UI usable.
    }
  }, [storageKey, value]);

  return [value, setValue] as const;
}
