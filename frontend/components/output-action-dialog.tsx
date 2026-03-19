"use client";

import * as React from "react";
import { LoaderCircle, Sparkles, TriangleAlert } from "lucide-react";

import { useFeedback } from "@/components/feedback-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
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

export interface OutputActionDialogPrefill {
  overwrite?: boolean;
  promptTemplate?: string;
  sampleCap?: number | string;
  targetField?: string;
}

interface VlmTaggingFormState {
  overwrite: boolean;
  promptTemplate: string;
  sampleCap: string;
  targetField: string;
}

const DEFAULT_PROMPT_TEMPLATE =
  "Generate concise tags that describe the main scene content and notable entities.";

function getDefaultTargetField(output: OutputDetail | null) {
  if (!output) {
    return "image";
  }

  if (output.format === "json") {
    return "labels";
  }

  if (output.format === "tfrecord") {
    return "image";
  }

  return "camera_front_image";
}

export function getDefaultOutputActionPrefill(
  outputs: OutputDetail[],
): Required<OutputActionDialogPrefill> {
  const primaryOutput = outputs[0] ?? null;

  return {
    overwrite: false,
    promptTemplate: DEFAULT_PROMPT_TEMPLATE,
    sampleCap: 24,
    targetField: getDefaultTargetField(primaryOutput),
  };
}

function createDefaultFormState(
  outputs: OutputDetail[],
  prefill?: OutputActionDialogPrefill,
): VlmTaggingFormState {
  const defaults = getDefaultOutputActionPrefill(outputs);

  return {
    overwrite: prefill?.overwrite ?? defaults.overwrite,
    promptTemplate: prefill?.promptTemplate?.trim() || defaults.promptTemplate,
    sampleCap: String(prefill?.sampleCap ?? defaults.sampleCap),
    targetField: prefill?.targetField?.trim() || defaults.targetField,
  };
}

export function OutputActionDialog({
  onCreated,
  onOpenChange,
  open,
  outputs,
  prefill,
}: {
  onCreated?: (actions: OutputActionDetail[]) => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  outputs: OutputDetail[];
  prefill?: OutputActionDialogPrefill;
}) {
  const { notify } = useFeedback();
  const { error, isCreating, reset, trigger } = useCreateOutputAction();
  const outputIdsKey = React.useMemo(() => outputs.map((output) => output.id).join("|"), [outputs]);
  const [formState, setFormState] = React.useState<VlmTaggingFormState>(() =>
    createDefaultFormState(outputs, prefill),
  );

  React.useEffect(() => {
    if (!open) {
      setFormState(createDefaultFormState(outputs, prefill));
      reset();
      return;
    }

    setFormState(createDefaultFormState(outputs, prefill));
  }, [
    open,
    outputIdsKey,
    prefill?.overwrite,
    prefill?.promptTemplate,
    prefill?.sampleCap,
    prefill?.targetField,
    outputs,
    prefill,
    reset,
  ]);

  const outputCount = outputs.length;
  const primaryOutput = outputs[0] ?? null;
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
    outputCount === 0 ||
    isCreating ||
    !normalizedTargetField ||
    !normalizedPromptTemplate ||
    Boolean(sampleCapError);
  const createLabel =
    outputCount === 1 ? "Run VLM tagging" : `Queue ${outputCount} tagging actions`;

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (submitDisabled) {
      return;
    }

    const createdActions: OutputActionDetail[] = [];

    try {
      for (const output of outputs) {
        const createdAction = await trigger(output.id, {
          action_type: "vlm_tagging",
          config: {
            overwrite: formState.overwrite,
            prompt_template: normalizedPromptTemplate,
            sample_cap: Math.floor(sampleCapValue),
            target_field: normalizedTargetField,
          },
        });

        createdActions.push(createdAction);
      }

      notify({
        description:
          outputCount === 1
            ? `Queued VLM tagging for ${primaryOutput?.file_name ?? "the selected output"}.`
            : `Queued VLM tagging for ${outputCount} selected outputs.`,
        title: "Output action created",
        tone: "success",
      });
      onCreated?.(createdActions);
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
            {outputCount === 1
              ? `Create a durable output action for ${primaryOutput?.file_name ?? "the selected output"} and surface its progress in the outputs workspace.`
              : `Create durable output actions for ${outputCount} selected outputs and monitor them together in the outputs workspace.`}
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

          {outputCount > 1 ? (
            <div className="space-y-3 rounded-lg border bg-muted/15 px-4 py-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{outputCount} outputs selected</Badge>
                <Badge variant="outline">{primaryOutput ? primaryOutput.format.toUpperCase() : "MIXED"}</Badge>
              </div>
              <div className="space-y-1 text-sm text-muted-foreground">
                {outputs.slice(0, 3).map((output) => (
                  <p className="break-all" key={output.id}>
                    {output.file_name}
                  </p>
                ))}
                {outputCount > 3 ? (
                  <p>Plus {outputCount - 3} more outputs in this batch.</p>
                ) : null}
              </div>
            </div>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="vlm-target-field">Target field</Label>
            <Input
              id="vlm-target-field"
              onChange={(event) =>
                setFormState((currentState) => ({ ...currentState, targetField: event.target.value }))
              }
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
              onChange={(event) =>
                setFormState((currentState) => ({ ...currentState, sampleCap: event.target.value }))
              }
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
              onCheckedChange={(checked) =>
                setFormState((currentState) => ({ ...currentState, overwrite: checked }))
              }
            />
          </div>

          <DialogFooter>
            <Button disabled={isCreating} onClick={() => onOpenChange(false)} type="button" variant="outline">
              Cancel
            </Button>
            <Button disabled={submitDisabled} type="submit">
              {isCreating ? <LoaderCircle className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              {createLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
