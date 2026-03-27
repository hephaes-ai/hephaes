import { AppProviders } from "@/components/app-providers";
import { AppShell } from "@/components/app-shell";
import "../src/styles/globals.css";

export const metadata = {
  description: "Local frontend for registering and inspecting ROS bag assets.",
  title: "Hephaes",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning className="antialiased">
      <body className="min-h-svh bg-background font-sans text-foreground">
        <AppProviders>
          <AppShell>{children}</AppShell>
        </AppProviders>
      </body>
    </html>
  );
}
