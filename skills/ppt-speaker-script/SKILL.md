---
name: ppt-speaker-script
description: Write or revise a read-aloud speaker script for a generated or imported ppt-generator deck, save it as speaker notes, and export the matching Markdown script. Use for presenter notes, narration, speaking scripts, or 발표 대본 and 스피커 스크립트 requests, including the script stage of a complete deck.
---

# Speaker scripts for ppt-generator

Write what the presenter will actually say while showing the finished slides.
This skill owns spoken wording and review. The server owns deck inputs, output
schemas, validation, and deterministic storage/export. Do not copy the JSON
schema into this skill or regenerate slide designs to change notes.

Read [the writing guide](references/speaker-script-guide.md) before drafting or
revising. It adapts the supplied SPEAKER-SCRIPT-GUIDE.md into reusable instructions
without customer names, adoption claims, or dependence on a local source file.

## Establish the delivery brief

Use the user's request, saved presentation context, and supplied notes to establish
language, audience, purpose, content time, question time, and who closes the session.
Honor explicit preferences; infer routine details from context. Ask only for a
missing detail that would materially change the script. Do not invent a host,
presenter experience, customer situation, or a presentation duration.

The source guide's English, non-native presenter, small online meeting is a
**delivery profile**, not a universal restriction. Apply its breath-line and
100 words/minute starting point when that profile fits. Preserve a different
language or presentation style requested by the user. Keep existing notes as
source material; revise only the requested scope. For a narrow edit, return all
slides but copy unaffected notes verbatim. A silent slide may keep empty notes.

## Draft from the actual deck

1. If the deck has not been designed or imported, finish that step with `ppt-design`
   or `ppt-modify`. Do not write a final script from an imagined visual layout.
2. Call `mcp__ppt-generator__prepare_speaker_script(project_id, brief)` with the
   user's delivery requirements. The response includes actual design specs,
   existing notes, outline sources/assumptions where available, presentation
   context, `response_schema`, and `script_context`.
3. Generate JSON matching that returned `response_schema`. Use the server's
   `system_prompt` and `user_prompt` together with the writing guide. Keep all
   slide indices 1-based. Cover every slide exactly once, including silent slides.
   Put only spoken words and meaningful line breaks in `speaker_notes`.
   If an image or diagram carries meaning that the supplied text does not explain,
   inspect its local image or existing slide preview before writing about it.
   `mcp__ppt-generator__load_design_spec(project_id)` provides the spec directory
   when relative asset paths need resolving. Do not infer image content from a filename;
   identify missing visual evidence if it cannot be inspected.
4. Review the **whole sequence**, especially each slide's last two lines and the
   next slide's first two lines. Correct in-scope factual, flow, and wording issues
   before saving. Preserve greetings, question openings, closing signals, and
   host handoffs when they serve the actual conversation.
5. Call `mcp__ppt-generator__ingest_speaker_script(project_id, script_json, script_context)`.
   Echo the prepared `script_context` unchanged. A schema error requires correction;
   a stale context requires a new prepare and a review against the current deck.
   Never reuse a result after slide content, order, evidence, or briefing changed.

The server saves only notes, synchronizes outline notes when an outline exists,
and creates `speaker-script.md` from those same saved notes. Imported decks do not
need an outline. Ingest does not refresh previously exported HTML/PPTX files;
perform the completion checkpoint below.

## Check time without damaging speech

For English read-aloud scripts, expand numbers into their actual spoken form and
use Python to count the spoken words and estimate time. The server's `word_counts`
are whitespace-separated tokens, not a multilingual speaking-time measurement.
Use a user-supplied rate or rehearsal result where available. For other languages,
use a suitable agreed measure or report that time still needs a read-through;
do not apply English words/minute automatically.

For the small-online non-native English profile, start near 100 words/minute,
allow at least one second per slide transition, include planned pauses, and reserve
about 10% of content time. The guide gives the calculation. Remove duplicated
points and optional tangents first. Do not shave words into unnatural fragments.
If fixed time and required content cannot both fit, explain the scope decision
needed; do not silently lengthen the session or remove required content.

## Completion checkpoint

- Within a complete deck workflow, return control to `ppt-design` for deck review,
  Visual QA, and final export. Respect a request to omit script generation.
- For a standalone script request, finish the notes edit, then call
  `mcp__ppt-generator__export_speaker_script(project_id)`,
  `mcp__ppt-generator__export_html(project_id=project_id)`, and
  `mcp__ppt-generator__export_pptx(project_id=project_id)` from the same saved deck.
  Open the final HTML with the user's normal delivery method unless instructed otherwise.
- After slide edits, additions, deletion, or moves, recheck the affected script and
  its neighboring transitions. Re-export Markdown at the stable checkpoint even
  if no wording changed, so titles and order match the current deck.
- Deliver the Markdown and deck paths, language/profile used, and any unresolved
  timing or evidence limitation. Do not claim a spoken rehearsal or model-quality
  improvement from schema tests or calculated timing alone.
