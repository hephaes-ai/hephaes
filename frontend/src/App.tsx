import { BrowserRouter } from "react-router-dom"

import { AppProviders } from "@/components/app-providers"
import { AppShell } from "@/components/app-shell"
import { DesktopRoutes } from "@/routes/desktop-routes"

export default function App() {
  return (
    <BrowserRouter>
      <AppProviders>
        <AppShell>
          <DesktopRoutes />
        </AppShell>
      </AppProviders>
    </BrowserRouter>
  )
}
