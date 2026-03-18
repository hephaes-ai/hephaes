# Frontend UI Guidelines

## Goal

Keep the frontend consistent across phases by standardizing on shadcn-based building blocks, a minimal visual language, and first-class theme support.

## Component Strategy

Use shadcn components whenever a suitable primitive or composed component already exists.

Preferred examples include:

- `Button`
- `Input`
- `Textarea`
- `Label`
- `Select`
- `Checkbox`
- `Switch`
- `Table`
- `Card`
- `Badge`
- `Dialog`
- `Sheet`
- `DropdownMenu`
- `Tabs`
- `Tooltip`
- `Toast`
- `Skeleton`

Custom components are fine when the product needs domain-specific behavior, but they should still be composed from shadcn primitives whenever practical instead of introducing a separate design system.

## Visual Direction

Keep the UI minimal and clean:

- prioritize whitespace, alignment, and typography over decoration
- keep color usage restrained and functional
- use subtle borders, muted surfaces, and low-contrast separators instead of heavy chrome
- prefer simple tables, cards, drawers, and dialogs over dense custom layouts
- avoid ornamental gradients, large shadows, and overly playful motion unless a later phase explicitly needs them
- favor readability and fast scanning over visual novelty

The app should feel calm, utilitarian, and polished rather than flashy.

## Dark Mode

Dark mode is a required part of the frontend plan, not a nice-to-have.

Requirements:

- support light mode and dark mode from the main app shell
- provide a visible theme toggle in the header or equivalent global navigation area
- persist the user theme preference locally
- allow a reasonable system-theme default on first load
- ensure shadcn tokens, surfaces, borders, charts, scrubbers, and embedded visualization panels remain legible in both themes

## Accessibility and Consistency

Across phases:

- keep contrast and focus states clear in both themes
- use consistent spacing and sizing scales
- keep destructive actions visually distinct but still restrained
- avoid introducing multiple competing interaction patterns for the same kind of task

## Phase Integration

Each frontend phase should assume these guidelines unless a phase explicitly calls out a justified exception.
