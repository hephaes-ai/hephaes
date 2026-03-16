"use client";

import * as React from "react";
import { CheckCircle2, Info, TriangleAlert, X } from "lucide-react";

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

type FeedbackTone = "error" | "info" | "success";

interface FeedbackMessage {
  description?: string;
  id: string;
  title: string;
  tone: FeedbackTone;
}

interface FeedbackInput {
  description?: string;
  title: string;
  tone?: FeedbackTone;
}

interface FeedbackContextValue {
  dismiss: (id: string) => void;
  notify: (message: FeedbackInput) => void;
}

const FeedbackContext = React.createContext<FeedbackContextValue | null>(null);

function createMessageId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function getAlertToneClasses(tone: FeedbackTone) {
  if (tone === "success") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200";
  }

  if (tone === "info") {
    return "border-border bg-card";
  }

  return "";
}

function getAlertIcon(tone: FeedbackTone) {
  if (tone === "success") {
    return <CheckCircle2 className="size-4" />;
  }

  if (tone === "error") {
    return <TriangleAlert className="size-4" />;
  }

  return <Info className="size-4" />;
}

export function FeedbackProvider({ children }: { children: React.ReactNode }) {
  const [messages, setMessages] = React.useState<FeedbackMessage[]>([]);
  const timeoutIds = React.useRef<number[]>([]);

  React.useEffect(() => {
    return () => {
      for (const timeoutId of timeoutIds.current) {
        window.clearTimeout(timeoutId);
      }
    };
  }, []);

  function dismiss(id: string) {
    setMessages((currentMessages) => currentMessages.filter((message) => message.id !== id));
  }

  function notify(message: FeedbackInput) {
    const id = createMessageId();
    const nextMessage: FeedbackMessage = {
      description: message.description,
      id,
      title: message.title,
      tone: message.tone ?? "info",
    };

    setMessages((currentMessages) => [...currentMessages, nextMessage].slice(-3));

    const timeoutId = window.setTimeout(() => {
      dismiss(id);
      timeoutIds.current = timeoutIds.current.filter((value) => value !== timeoutId);
    }, 5000);

    timeoutIds.current.push(timeoutId);
  }

  return (
    <FeedbackContext.Provider value={{ dismiss, notify }}>
      {children}
      <div className="pointer-events-none fixed inset-x-4 top-20 z-50 mx-auto flex max-w-md flex-col gap-2">
        {messages.map((message) => (
          <Alert
            key={message.id}
            className={`pointer-events-auto shadow-sm ${getAlertToneClasses(message.tone)}`}
            variant={message.tone === "error" ? "destructive" : "default"}
          >
            {getAlertIcon(message.tone)}
            <AlertTitle>{message.title}</AlertTitle>
            {message.description ? <AlertDescription>{message.description}</AlertDescription> : null}
            <AlertAction>
              <Button
                aria-label={`Dismiss ${message.title}`}
                onClick={() => dismiss(message.id)}
                size="icon-xs"
                type="button"
                variant="ghost"
              >
                <X className="size-3.5" />
              </Button>
            </AlertAction>
          </Alert>
        ))}
      </div>
    </FeedbackContext.Provider>
  );
}

export function useFeedback() {
  const context = React.useContext(FeedbackContext);

  if (!context) {
    throw new Error("useFeedback must be used inside FeedbackProvider.");
  }

  return context;
}
