"use client"

import { Menu } from "lucide-react"

import { BackendStatus } from "@/components/backend-status"
import { BackendConnectionNotice } from "@/components/backend-connection-notice"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { AppLink, useAppPathname } from "@/lib/app-routing"

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = useAppPathname()
  const isDashboardRoute = pathname === "/" || pathname === "/dashboard"
  const isInventoryRoute = pathname === "/inventory"
  const isJobsRoute = pathname === "/jobs" || pathname.startsWith("/jobs/")
  const isOutputsRoute =
    pathname === "/outputs" || pathname.startsWith("/outputs/")

  return (
    <div className="flex min-h-svh flex-col bg-background">
      <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/90">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-4">
            <div className="min-w-0">
              <AppLink
                className="flex items-center gap-2 text-sm font-semibold tracking-tight text-foreground"
                href="/dashboard"
              >
                <span className="relative block size-8 shrink-0">
                  <img
                    alt=""
                    aria-hidden="true"
                    className="size-full object-contain dark:hidden"
                    src="/robot-head-logo-iso.png"
                  />
                  <img
                    alt=""
                    aria-hidden="true"
                    className="hidden size-full object-contain dark:block"
                    src="/robot-head-logo-dark-bg.png"
                  />
                </span>
                <span>Hephaes</span>
              </AppLink>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  aria-label="Navigation menu"
                  className="sm:hidden"
                  size="sm"
                  variant="ghost"
                >
                  <Menu className="size-5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuItem asChild>
                  <AppLink href="/dashboard">Dashboard</AppLink>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <AppLink href="/inventory">Inventory</AppLink>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <AppLink href="/outputs">Outputs</AppLink>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <AppLink href="/jobs">Jobs</AppLink>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <nav className="hidden sm:flex">
              <div className="flex items-center gap-1">
                <Button
                  asChild
                  size="sm"
                  variant={isDashboardRoute ? "secondary" : "ghost"}
                >
                  <AppLink href="/dashboard">Dashboard</AppLink>
                </Button>
                <Button
                  asChild
                  size="sm"
                  variant={isInventoryRoute ? "secondary" : "ghost"}
                >
                  <AppLink href="/inventory">Inventory</AppLink>
                </Button>
                <Button
                  asChild
                  size="sm"
                  variant={isOutputsRoute ? "secondary" : "ghost"}
                >
                  <AppLink href="/outputs">Outputs</AppLink>
                </Button>
                <Button
                  asChild
                  size="sm"
                  variant={isJobsRoute ? "secondary" : "ghost"}
                >
                  <AppLink href="/jobs">Jobs</AppLink>
                </Button>
              </div>
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
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 sm:px-6">
        <BackendConnectionNotice />
        {children}
      </main>
    </div>
  )
}
