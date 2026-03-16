"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { BackendStatus } from "@/components/backend-status";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isInventoryRoute = pathname === "/";

  return (
    <div className="flex min-h-svh flex-col bg-background">
      <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/90">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-4">
            <div className="min-w-0">
              <Link className="block text-sm font-semibold tracking-tight text-foreground" href="/">
                Hephaes
              </Link>
              <p className="truncate text-xs text-muted-foreground">Local asset inventory</p>
            </div>
            <nav className="hidden sm:flex">
              <Button asChild size="sm" variant={isInventoryRoute ? "secondary" : "ghost"}>
                <Link href="/">Inventory</Link>
              </Button>
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden md:block">
              <BackendStatus />
            </div>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 sm:px-6">{children}</main>
    </div>
  );
}
