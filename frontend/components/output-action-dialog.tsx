"use client";

import * as React from "react";
import { LoaderCircle, Sparkles, TriangleAlert } from "lucide-react";

import { useFeedback } from "@/components/feedback-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useCreateOutputAction } from "@/hooks/use-backend";
import type { OutputActionDetail, OutputDetail } from "@/lib/api";
import { getErrorMessage } from "@/lib/api";

interface VlmTaggingFormState {
  overwrite: boolean;
  promptTemplate: string;
  sampleCap: string;
  targetField: string;
}

function createDefaultFormState(output: OutputDetail | null): VlmTaggingFormState {
  return {
    overwrite: false,
    promptTemplate: "Generate concise tags that describe the main scene content and notable entities.",
    sampleCap: "24",
    targetField:
      output?.format === "json"
        ? "labels"
        : output?.format === "tfrecord"
          ? "image"
          : "camera_front_image",
  };
}

export function OutputActionDialog({
  onCreated,
  onOpenChange,
  open,
  output,
}: {
  onCreated?: (action: OutputActionDetail) => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  output: OutputDetail | null;
}) {
  const { notify } = useFeedback();
  const { error, isCreating, reset, trigger } = useCreateOutputAction();
  const [formState, setFormState] = React.useState<VlmTaggingFormState>(() =>
    createDefaultFormState(output),
  );

  React.useEffect(() => {
    if (!open) {
      setFormState(createDefaultFormState(output));
      reset();
    }
  }, [open, output, reset]);

  React.useEffect(() => {
    if (!open || !output) {
      return;
    }

    setFormState((currentState) => ({
      ...currentState,
      targetField: currentState.targetField.trim() ? currentState.targetField : createDefaultFormState(output).targetField,
    }));
  }, [open, output]);

  const normalizedTargetField = formState.targetField.trim();
  const normalizedPromptTemplate = formState.promptTemplate.trim();
  const sampleCapValue = Number(formState.sampleCap);
  const sampleCapError =
    !Number.isFinite(sampleCapValue) || sampleCapValue <= 0
      ? "Sample cap must be a number greater than zero."
      : sampleCapValue > 5000
        ? "Sample cap must stay below 5000 for this first-pass flow."
        : null;
  const submitDisabled =
    !output ||
    isCreating ||
    !normalizedTargetField ||
    !normalizedPromptTemplate ||
    Boolean(sampleCapError);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!output || submitDisabled) {
      return;
    }

    try {
      const createdAction = await trigger(output.id, {
        action_type: "vlm_tagging",
        config: {
          overwrite: formState.overwrite,
          prompt_template: normalizedPromptTemplate,
          sample_cap: Math.floor(sampleCapValue),
          target_field: normalizedTargetField,
        },
      });

      notify({
        description: `Queued VLM tagging for ${output.file_name}.`,
        title: "Output action created",
        tone: "success",
      });
      onCreated?.(createdAction);
      onOpenChange(false);
    } catch (submitError) {
      notify({
        description: getErrorMessage(submitError),
        title: "Could not start VLM tagging",
        tone: "error",
      });
    }
  }

  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="size-4" />
            Run VLM tagging
          </DialogTitle>
          <DialogDescription>
            Create a durable output action for {output?.file_name ?? "the selected output"} and surface its progress in
            the outputs workspace.
          </DialogDescription>
        </DialogHeader>

        <form className="space-y-4" onSubmit={onSubmit}>
          {error ? (
            <Alert variant="destructive">
              <TriangleAlert className="size-4" />
              <AlertTitle>Could not start action</AlertTitle>
              <AlertDescription>{getErrorMessage(error)}</AlertDescription>
            </Alert>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="vlm-target-field">Target field</Label>
            <Input
              id="vlm-target-field"
              onChange={(event) => setFormState((currentState) => ({ ...currentState, targetField: event.target.value }))}
              placeholder="image"
              value={formState.targetField}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="vlm-prompt-template">Prompt template</Label>
            <Textarea
              id="vlm-prompt-template"
              onChange={(event) =>
                setFormState((currentState) => ({ ...currentState, promptTemplate: event.target.value }))
              }
              rows={5}
              value={formState.promptTemplate}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="vlm-sample-cap">Sample cap</Label>
            <Input
              id="vlm-sample-cap"
              min="1"
              onChange={(event) => setFormState((currentState) => ({ ...currentState, sampleCap: event.target.value }))}
              step="1"
              type="number"
              value={formState.sampleCap}
            />
            {sampleCapError ? <p className="text-sm text-destructive">{sampleCapError}</p> : null}
          </div>

          <div className="flex items-center justify-between gap-4 rounded-lg border bg-muted/15 px-3 py-3">
            <div className="space-y-1">
              <Label htmlFor="vlm-overwrite">Overwrite existing tags</Label>
              <p className="text-sm text-muted-foreground">
                Keep this off to make the first pass append-only in future backend implementations.
              </p>
            </div>
            <Switch
              checked={formState.overwrite}
              id="vlm-overwrite"
              onCheckedChange={(checked) => setFormState((currentState) => ({ ...currentState, overwrite: checked }))}
            />
          </div>

          <DialogFooter>
            <Button disabled={isCreating} onClick={() => onOpenChange(false)} type="button" variant="outline">
              Cancel
            </Button>
            <Button disabled={submitDisabled} type="submit">
              {isCreating ? <LoaderCircle className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              Run VLM tagging
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
