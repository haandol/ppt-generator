# Quality and delivery

Use the user's brief and current DESIGN.md to judge the result. Renderer warnings,
geometry and the screenshot supply evidence; they are not interchangeable verdicts.

- Schema/reference errors require repair. Lint is diagnostic and does not itself edit
  the spec. Keep an intentional design when a heuristic warning has no visible defect.
- Complete-deck work includes read-only Visual QA and issue-scoped visual patches.
  저위험 시각 patch는 자동 적용한다. Use the visual QA skill for that protocol.
- Visual QA patches preserve text, data, element count/order, slide count and semantic
  links. Content/structure edits use the appropriate modify or script tool. If the user
  already requested that edit, reuse the authorization; ask only when the repair changes
  scope or intent beyond the existing request. Do not ask again for the same decision.
- Finish independent safe fixes, recheck their actual effects and disclose remaining
  medium/high issues. An unresolved issue is not permission to erase required content.

At the stable completion checkpoint, export current speaker-script Markdown, HTML and
PPTX from the saved deck. If a finalizer has just produced an output and its inputs have
not changed, reuse that output instead of rendering it again. Refresh any output whose
notes, content, title, order or visual spec changed. Keep one saved source of notes.

Open the final HTML by the user's delivery preference; a local HTML normally uses the
OS default opener. Honor explicit no-open or partial-output requests.
Browser automation/capture uses an isolated context or stable task-owned tab connection;
do not rely on the user's active window or ask them to pause other work.

Share paths and material unresolved issues. State which checks actually ran. Schema
validation, coordinates and successful rendering do not establish model-quality gains,
pixel fidelity, factual source verification or a spoken rehearsal.
