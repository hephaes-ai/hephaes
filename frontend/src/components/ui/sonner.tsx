"use client"

import { useTheme } from "next-themes"
import { Toaster as Sonner, type ToasterProps, toast } from "sonner"

function Toaster({ ...props }: ToasterProps) {
  const { theme = "system" } = useTheme()

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      toastOptions={{
        classNames: {
          description: "text-muted-foreground",
          toast: "group border-border bg-card text-card-foreground shadow-lg",
        },
      }}
      {...props}
    />
  )
}

export { Toaster, toast }
