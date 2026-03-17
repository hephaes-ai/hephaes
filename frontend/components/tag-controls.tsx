"use client";

import * as React from "react";
import { Plus, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import type { TagSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

function sortTags(tags: TagSummary[]) {
  return [...tags].sort((left, right) => left.name.localeCompare(right.name, undefined, { sensitivity: "base" }));
}

export function TagBadgeList({
  className,
  emptyLabel,
  maxVisible,
  onRemove,
  removable = false,
  tags,
}: {
  className?: string;
  emptyLabel?: string;
  maxVisible?: number;
  onRemove?: (tag: TagSummary) => void;
  removable?: boolean;
  tags: TagSummary[];
}) {
  if (tags.length === 0) {
    return emptyLabel ? <p className={cn("text-sm text-muted-foreground", className)}>{emptyLabel}</p> : null;
  }

  const visibleTags = maxVisible ? tags.slice(0, maxVisible) : tags;
  const hiddenTagCount = tags.length - visibleTags.length;

  return (
    <div className={cn("flex flex-wrap gap-2", className)}>
      {visibleTags.map((tag) => (
        <Badge key={tag.id} className={cn(removable && "gap-1 pr-1")} variant="outline">
          {tag.name}
          {removable && onRemove ? (
            <button
              aria-label={`Remove ${tag.name}`}
              className="rounded-full p-0.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={() => onRemove(tag)}
              type="button"
            >
              <X className="size-3" />
            </button>
          ) : null}
        </Badge>
      ))}
      {hiddenTagCount > 0 ? <Badge variant="secondary">+{hiddenTagCount}</Badge> : null}
    </div>
  );
}

export function TagActionPanel({
  applyButtonLabel,
  availableTags,
  createButtonLabel,
  createInputLabel,
  disabled = false,
  emptyState,
  excludeTagIds = [],
  onApplyTag,
  onCreateTag,
  selectLabel,
}: {
  applyButtonLabel: string;
  availableTags: TagSummary[];
  createButtonLabel: string;
  createInputLabel: string;
  disabled?: boolean;
  emptyState?: string;
  excludeTagIds?: string[];
  onApplyTag: (tagId: string) => Promise<void>;
  onCreateTag: (name: string) => Promise<void>;
  selectLabel: string;
}) {
  const selectId = React.useId();
  const createInputId = React.useId();
  const [isApplyingTag, setIsApplyingTag] = React.useState(false);
  const [isCreatingTag, setIsCreatingTag] = React.useState(false);
  const [newTagName, setNewTagName] = React.useState("");
  const [selectedTagId, setSelectedTagId] = React.useState("");

  const assignableTags = React.useMemo(() => {
    const excludedTagIds = new Set(excludeTagIds);
    return sortTags(availableTags).filter((tag) => !excludedTagIds.has(tag.id));
  }, [availableTags, excludeTagIds]);

  React.useEffect(() => {
    if (assignableTags.some((tag) => tag.id === selectedTagId)) {
      return;
    }

    setSelectedTagId(assignableTags[0]?.id ?? "");
  }, [assignableTags, selectedTagId]);

  async function handleApplyTag() {
    if (!selectedTagId) {
      return;
    }

    setIsApplyingTag(true);
    try {
      await onApplyTag(selectedTagId);
    } finally {
      setIsApplyingTag(false);
    }
  }

  async function handleCreateTag() {
    const trimmedName = newTagName.trim();
    if (!trimmedName) {
      return;
    }

    setIsCreatingTag(true);
    try {
      await onCreateTag(trimmedName);
      setNewTagName("");
    } finally {
      setIsCreatingTag(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
        <div className="space-y-2">
          <Label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor={selectId}>
            {selectLabel}
          </Label>
          <NativeSelect
            disabled={disabled || isApplyingTag || assignableTags.length === 0}
            id={selectId}
            onChange={(event) => setSelectedTagId(event.target.value)}
            value={selectedTagId}
          >
            <option value="">{assignableTags.length === 0 ? "No tags available" : "Select a tag"}</option>
            {assignableTags.map((tag) => (
              <option key={tag.id} value={tag.id}>
                {tag.name}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="flex items-end">
          <Button
            disabled={disabled || isApplyingTag || !selectedTagId}
            onClick={() => void handleApplyTag()}
            size="sm"
            type="button"
            variant="outline"
          >
            {applyButtonLabel}
          </Button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
        <div className="space-y-2">
          <Label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor={createInputId}>
            {createInputLabel}
          </Label>
          <Input
            disabled={disabled || isCreatingTag}
            id={createInputId}
            onChange={(event) => setNewTagName(event.target.value)}
            placeholder="New tag name"
            value={newTagName}
          />
        </div>
        <div className="flex items-end">
          <Button
            disabled={disabled || isCreatingTag || newTagName.trim().length === 0}
            onClick={() => void handleCreateTag()}
            size="sm"
            type="button"
            variant="outline"
          >
            <Plus className="size-3.5" />
            {createButtonLabel}
          </Button>
        </div>
      </div>

      {assignableTags.length === 0 && emptyState ? (
        <p className="text-sm text-muted-foreground">{emptyState}</p>
      ) : null}
    </div>
  );
}
