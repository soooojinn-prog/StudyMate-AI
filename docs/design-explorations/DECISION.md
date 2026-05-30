# Design Direction — Decision Record

- **Date:** 2026-05-30
- **Status:** Accepted
- **Affects:** Plan 4 (Study UI), Plan 5 (Dashboard), Plan 7 (Polish)

## Decision

The frontend UI from Plan 4 onward will be built in the **Architectural Dark / Blueprint** direction (`2026-05-30-study-session-architectural-dark.html`).

## Variants Considered

| Variant | File | Verdict |
|---|---|---|
| Editorial Paper (warm beige, EB Garamond, jʌungvermillion accent) | `2026-05-30-study-session-editorial.html` | Rejected — too book-like for an interactive tool |
| Architectural Dark (deep navy, Fraunces + JetBrains Mono, cyan + amber) | `2026-05-30-study-session-architectural-dark.html` | **Accepted** |

## Core Design Tokens (carry into Plan 4)

```
background:  #0A0D13   (deep navy-black with subtle cyan blueprint grid)
panel:       #11151F   (slightly elevated surface)
panel-line:  #1C2230   (1px hairlines)

text:        #E6E8EC   (primary)
text-mid:    #8A91A0   (secondary)
text-soft:   #545B6B   (meta / labels)

cyan:        #6BD7E1   (primary accent — actions, focus, success)
cyan-deep:   #2A8A93   (gradient anchor, hover dimming)
amber:       #E8AE5C   (warning / partial-credit signal)
magenta:     #D96F9A   (reinforcement / feedback callout)
red:         #EE6A6A   (error / miss)

grid color:  rgba(107, 215, 225, 0.07)
```

## Fonts

- **Display:** Fraunces (Google Fonts) — variable serif, italic for numbers and section markers. Use opsz axis (~144 at large sizes).
- **Body (Korean):** Pretendard Variable
- **Body (Latin):** falls through to Pretendard's Latin glyphs; if a refined alternative is needed in Plan 4+, evaluate Inter Tight or IBM Plex Sans.
- **Mono:** JetBrains Mono — used for meta labels, scores, timestamps, kbd hints.

## Layout Patterns

- Sticky left rail (~220px) for session meta + model versions + progress
- Asymmetric main grid; numeric headings get italic Fraunces at clamp(72px, 10vw, 116px)
- Section dividers as `NN Section ─── meta` row in mono caps
- Corner crops on the active question block ("crop marks" architectural detail)
- Buttons: bordered ghost by default; primary inverts to cyan ground

## What NOT to use (avoid generic AI slop)

- ❌ Purple/violet gradients on white
- ❌ Inter, Roboto, system-ui as primary
- ❌ Rounded-2xl card stacks with drop shadows
- ❌ Emoji icons in place of typographic markers
- ❌ Hanja section sigils (the editorial v1 used these; user feedback explicitly rejected)

## Implementation Notes for Plan 4

- shadcn/ui will be introduced in Plan 4. Override its default tokens with the palette above before generating any component.
- Score animations should use safe DOM (text node + appended span), not innerHTML.
- The architectural-dark HTML file is the **visual reference** — do not port HTML verbatim; rebuild as React server/client components per Next.js conventions.
