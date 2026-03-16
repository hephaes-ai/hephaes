"use client";

import * as React from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { Switch } from "@/components/ui/switch";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  const isDarkMode = mounted && resolvedTheme === "dark";

  return (
    <div className="flex items-center gap-2 rounded-full border bg-background/80 px-2.5 py-1.5 text-xs text-muted-foreground shadow-sm backdrop-blur-sm transition-[background-color,border-color,color] duration-200 ease-out">
      <Sun className={`size-3.5 transition-colors duration-200 ${isDarkMode ? "text-muted-foreground/60" : "text-foreground"}`} />
      <Switch
        aria-label={mounted ? `Toggle ${isDarkMode ? "light" : "dark"} mode` : "Toggle theme"}
        checked={isDarkMode}
        onCheckedChange={(checked) => setTheme(checked ? "dark" : "light")}
        size="sm"
      />
      <Moon className={`size-3.5 transition-colors duration-200 ${isDarkMode ? "text-foreground" : "text-muted-foreground/60"}`} />
      <span className="hidden sm:inline">{mounted ? (isDarkMode ? "Dark" : "Light") : "Theme"}</span>
    </div>
  );
}
