# Read-aloud script writing guide

Adapted from SPEAKER-SCRIPT-GUIDE.md. The original working profile is a non-native
English presenter reading during a small online technical introduction. The rules
below separate that profile from guidance that applies to other presentations.

## 1. Brief, grounding, and scope

Before writing, establish audience roles and language proficiency, the session's
purpose and expected next action, confirmed facts versus assumptions, total time
versus content/Q&A time, required scope, and question/host responsibilities. Use
existing context rather than a mandatory questionnaire. Also account for camera,
screen sharing, pointer use, and the user's distribution format where relevant.

Use the actual slide text, diagrams, linked material, and provided sources. Do not
invent a customer's environment, product requirements, organization, goals,
adoption results, or the presenter's experience. An unverified situation can be
explained as an explicit condition or hypothetical example. "Most customers",
"industry standard", "from anywhere", and performance claims still need evidence;
softening a sentence with "usually" does not verify it.

Preserve numbers, units, measurement conditions, dates, limits such as "up to",
and uncertainty. Keep a claim/source/date/condition/public-use record in working
material when claims need verification. It is not part of the spoken notes. Use
approved case evidence only when supplied; do not add customer names or adoption
claims from examples in a guide.

For an introduction, explain what the service does and its supported limits.
Mention a required subject accurately without drifting into a full design session.
An approximate diagram can explain where pieces sit while leaving detailed design
for a later discussion. Add a follow-up proposal only if the presenter's role and
the actual session purpose support it.

## 2. Breath lines and pronounceable language

For the source read-aloud profile, use one breath per explicit line, often about
8–12 English words. Treat that range as a starting point, not a quota. Keep names,
units, negation, and meaningful phrases together. A sentence may span lines; a
pause must not force the presenter to reconstruct its grammar. Use the same
line breaks in Markdown and speaker notes.

```text
Awkward pause:
Both are real,
before any result appears.

Complete thought before the pause:
And it takes real time and real money,
before any result appears.
```

Avoid repeatedly nesting "which", "that", "while", and "so that" clauses. Keep
one central thought per sentence and split when the subject or point changes.
Choose easy-to-pronounce verbs before delivery rather than offering emergency
substitutions inside the notes. Preserve official names and necessary technical
terms; expand unfamiliar abbreviations once when the audience needs the name.
Put pronunciation aids in a separate file only if requested.

Write numbers as spoken words for a read-aloud script: "five point three billion"
or "up to forty percent". The screen and speech must retain the same value,
unit, and qualifier. Do not introduce "up to" if the source makes an exact claim.

For a different language or delivery profile, use that language's natural phrase
boundaries and the presenter's preference. Do not force English word lengths or
hard line breaks onto a format designed for ordinary paragraphs.

## 3. Remove empty writing without flattening speech

Review connected meaning first, sentence structure second, and individual words
last. Smooth grammar cannot repair a missing reason or an unsupported conclusion.

Signals worth examining in context:

- Empty modifiers and verbs: "robust", "powerful", "seamless", "leverage", "unlock
  the full potential". State the specific operation or supported effect instead.
- Decorative contrast: "not just X but Y", "it's not X, it's Y". State the
  relationship directly unless an actual misunderstanding requires a contrast.
- A recap after every paragraph. Keep a closing signal when it finishes a promised
  multi-slide group; avoid repeating the same point within one explanation.
- Renaming the same thing as service/platform/solution/offering. Keep a stable
  name, then use a pronoun when the referent is clear.
- Uniform paragraph lengths and identical sentence patterns. Give important
  explanations room and keep bridging slides brief; do not manufacture variation.
- Empty transitions such as "Let's dive in". Receive a concrete idea from the
  previous slide and add the next relationship.

```text
Empty transition:
Now let's dive into the architecture.

Connected transition:
Those three pieces have to sit somewhere.
Here is where they sit.
```

After removing filler, restore natural connections. Starting a sentence with
"And", "So", "But", or "Now" is normal spoken English when the relationship
supports it. Use natural contractions, except where a fully spoken negation
is the intended emphasis. Explain cause and effect together when they read easily.

Use concrete objects and actions so listeners can picture the situation. Include
the presenter's observation only if their actual experience supports it; do not
force a quota of invented personal remarks. Vary breath-line length naturally
without turning the speech into slogans or isolated fragments.

Do not insert scripted "um", "you know", jokes, slang, self-deprecation, or stage
directions to imitate spontaneous speech. Read the result in the listener's order:
would the presenter actually say it in this meeting, and can the listener follow
what each new sentence adds?

## 4. Address the audience without assuming their situation

For an introductory first meeting, general subjects or conditional statements are
often safer than "your systems already use..." or "you need...". Choose the
addressing style from the user's brief rather than prohibiting second person for
every presentation. Greetings, gratitude, genuine audience questions, invitations,
and conversational handoffs may need direct address.

When replacing "you", do not put every sentence into passive voice. Use a clear
general actor, such as "the application reads the file". Keep passive voice when
the actor is irrelevant and it is the natural construction.

Avoid paired slogans, punctuation-driven lists such as "Storage. Speed. Security.",
dramatic punchlines, and self-answered rhetorical questions in the small-online
profile. Real questions are appropriate when the presenter will wait for an
answer. Do not erase useful discussion questions from an interactive session.

Do not declare the customer's goals on their behalf. Preserve a confirmed goal
with its source; otherwise describe the capability or condition rather than
inventing a population-wide goal.

## 5. Match the screen and connect slides

Explain the slide's message rather than reading its title and visible sentences
aloud. Follow the visual order so listeners can match speech to the screen.
Numbers are useful when the actual order or count matters, not as a repeated
"first/second/third" pattern on every slide. A sequence diagram or ordered procedure
may need explicit step language; independent points often do not.

Use ordinary words for a made-up diagram box name so it is not mistaken for an
official product term. When actual layout matters, refer to screen positions in
speech: "On the left...", "In the middle...", "On the right...". Only use positions
that match the supplied design. A pointer may be small or delayed online.

Do not read a wall of company logos or introduce unsupported adoption claims.
If supplied approved cases have a documented common point, state that point
briefly and let the following slide explain it.

For every transition, read the previous slide's last two lines and the next
slide's first two lines together. Check that:

- The listener has the context needed for the new subject, actor, or example.
- The preceding slide has not already concluded what the next slide is meant
  to establish, or defined what the next slide asks again.
- A promised group has a natural closing signal when it ends.
- A case introduction, opening phrase, or explanation is not unnecessarily repeated.

```text
Repeated introduction:
Previous slide: The example involves a document-processing application.
Next slide: Here is the story.

Connected opening:
Next slide: The application has to validate each document before storage.
```

This revision supplies the next action using the application already introduced;
the listener does not have to infer a new actor or hear the introduction again.
Do not move a conclusion ahead of its supporting explanation just to make a
bridge sentence sound decisive.

## 6. Online meetings and conversational signals

For a small online meeting, avoid staging that depends on visible audience
reactions, dramatic silence, or a response to "Does that make sense?". A real
check-in may still fit an interactive meeting; allow time and a usable response
channel. Account for slide-sharing delay in the timing plan rather than inserting
stage instructions into the spoken notes.

The opening should announce the actual question arrangement and approximate
content duration when known. The ending follows the presenter's responsibility:
open questions and wait, or close the introduction and hand back to the host.
Do not invent discovery questions or next steps if the host owns that discussion.

```text
For a confirmed host handoff:
That finishes the introduction.
Thank you for your time,
and I'll hand it back now.
```

Preserve brief greeting, gratitude, section-closing, and handoff expressions when
they tell the listener who speaks next. A sentence can be useful without adding a
new technical fact. Do not add an identical closing or confirmation question to
every answer or slide.

## 7. Time and scope

For a non-native English presenter reading online, start near 100 words/minute.
Adjust to the presenter's measured pace or explicit preference. Count only spoken
content, with numbers expanded into the words actually read. Keep pause and
transition estimates separate from a real rehearsal.

Use Python, not mental estimates, for calculations. For the source profile:

```python
spoken_minutes = spoken_words / speaking_rate_wpm
estimated_minutes = spoken_minutes + transition_seconds / 60 + planned_pause_seconds / 60
fits = estimated_minutes <= allotted_content_minutes * 0.9
```

Use at least one second per slide transition as a planning starting point.
For this profile, an estimated pace above 110 words/minute is a reason to review
scope or confirm that the presenter can maintain it. Other profiles may use a
different pace. A whitespace token count does not measure speaking time for every
language. Final duration requires reading the actual deck through at delivery pace.

Keep introductory background proportionate so it does not displace the main
content. Shorten duplicate points, optional tangents, and redundant slides before
editing meaningful phrases. Changing slide count or required scope needs the
user's direction. Never turn "with every access logged" into "logging access"
just to save words. Do not silently change the promised session duration.

## 8. Spoken artifact and final review

Keep only slide headings and words to say in the reading document. Store drafting
purpose, time calculations, pronunciation notes, claim records, and delivery cues
separately when needed; do not mix them into speaker_notes. Generate Markdown
from saved notes so its text, order, and line breaks match the deck.

Reference links can live on the closing slide when supplied and appropriate.
Use meaningful labels instead of reading long URLs. Match the screen order when
briefly explaining what each resource offers; do not invent a video or workshop.
Slide insertion, deletion, and reordering require a new current-order export.

Review sound, wording, continuity, grounding, scope, and delivery together. Correct
confirmed in-scope issues and reread the whole sequence. Wording searches are
candidate finders, not proof of quality. A warning about a contraction, direct
address, or repeated term cannot override a justified conversational function.
Do not claim an independent review, a performed rehearsal, or guaranteed absence
of AI-style prose unless that verification actually occurred.
