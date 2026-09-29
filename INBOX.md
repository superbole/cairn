# INBOX

- **Map Claude family and effort onto Cursor and Grok.** Captured 2026-09-29. Not decided. D45 still says Cursor `Auto` and any non-Anthropic model (Grok, Composer, GPT) is off the scale: name it and ask, do not call it above or below. D47 says the label is the family, Haiku < Sonnet < Opus < Fable, and effort is separate. The preamble says `high` is that model's thinking or Max variant and `medium` is the standard one, and to pick the current model of the family. It names no slug. The slugs below are the ones this session's subagent list offered on 2026-09-29. The picker may have more. A blank cell means it was not in that list, not that Cursor lacks it. Two Sonnet highs were both listed, so "current of the family" is not one slug.

| Claude label | effort | Cursor slug, Claude | Cursor slug, Grok |
|---|---|---|---|
| Haiku | high | `claude-4.5-haiku-thinking` | `grok-4.7-high` |
| Haiku | medium | | `cursor-grok-4.6-medium` |
| Sonnet | high | `claude-sonnet-5-5-high` and `claude-4.5-sonnet-thinking` | `grok-4.7-high` |
| Sonnet | medium | | `cursor-grok-4.6-medium` |
| Opus | high | `claude-opus-5-thinking-high` | `grok-4.7-high` |
| Opus | medium | `claude-opus-5-5-medium` | `cursor-grok-4.6-medium` |
| Fable | high | `claude-fable-5-1-thinking-high` | `grok-4.7-high` |
| Fable | medium | | `cursor-grok-4.6-medium` |

This chat ran as `grok-4.7-high`. The Grok column is the same two slugs on every row: effort only, not a family. Also in that list and also off the scale: `composer-2.5-fast`, `gemini-3.8-flash-high`, `gpt-5.6-sol-medium`, `muse-spark-1.3-high`. Triage should say whether the preamble names these slugs, and whether a Grok row is allowed to stand in for a Claude family or only records the effort.
