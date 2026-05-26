# Agenda Slide Optional Numbering

## Status

Accepted

## Context

Agenda slides always generated items with numbered format (e.g., "01 Overview", "02 Core Technology"). There was no way to produce an unnumbered agenda, which limited flexibility for presentations where a simpler bullet-list style is more appropriate.

## Decision

Make numbering on agenda slides optional. The design system prompt now instructs the LLM that items may use either numbered format or unnumbered format (bullet list / plain text), choosing whichever fits the presentation tone better.

## Changes

- `src/ppt_generator/interfaces/prompts/design_system_content.prompt.md`: Updated `<slide_type_agenda>` rules — changed "numbered items" to "items", added explicit guidance that numbering is optional.

## Consequences

- Agenda slides can now be generated with or without item numbers.
- Existing presentations are unaffected; the LLM may still choose numbered format when it fits.
- No schema or validation changes required — the underlying data model already supports both styles.
