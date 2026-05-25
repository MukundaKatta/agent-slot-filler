# agent-slot-filler

Fill named `{slot}` placeholders in template strings for LLM agents.

```python
from agent_slot_filler import AgentSlotFiller

filler = AgentSlotFiller()

template = "Hello, {name}! You have {count} messages."
result = filler.fill(template, {"name": "Alice", "count": "3"})
# "Hello, Alice! You have 3 messages."

# Partial fill — leave unfilled slots as-is
partial = filler.fill_partial(template, {"name": "Bob"})
# "Hello, Bob! You have {count} messages."

# Introspect slots
filler.slots_in(template)                      # ["count", "name"]
filler.missing_slots(template, {"name": "x"}) # ["count"]

# Strict validation
filler.validate(template, {"name": "x"})  # raises SlotError listing "count"
```

## Install

```bash
pip install agent-slot-filler
```

## Features

- Fill `{slot}` placeholders from a dict; values converted via `str()`
- `fill_partial` leaves unfilled slots in place (chainable two-pass filling)
- `slots_in(template)` — sorted unique slot names
- `missing_slots(template, values)` — slots without a value
- `filled_slots(template, values)` — slots that have a value
- `validate(template, values)` — raises `SlotError` listing all missing slots
- `is_complete`, `has_slots`, `slot_count` guard helpers
- `fill_many(templates, values)` and `fill_dict(templates, values)` batch helpers
- Escaped braces: `{{` → `{`, `}}` → `}` (only resolved on final `fill`)
- `strict=True` constructor/per-call flag raises on missing slots
- `default=` constructor arg replaces missing slots with a fallback string
- Module-level `fill()`, `slots_in()`, `missing_slots()` shortcuts
- Zero dependencies

## API

```python
f = AgentSlotFiller(*, strict=False, default=None)

f.fill(template, values, *, strict=None)  -> str
f.fill_partial(template, values)          -> str
f.fill_many(templates, values, ...)       -> list[str]
f.fill_dict(templates, values, ...)       -> dict[str, str]

f.slots_in(template)                      -> list[str]
f.missing_slots(template, values)         -> list[str]
f.filled_slots(template, values)          -> list[str]
f.validate(template, values)              -> None  # raises SlotError
f.is_complete(template, values)           -> bool
f.has_slots(template)                     -> bool
f.slot_count(template)                    -> int

# Module-level shortcuts
fill(template, values, *, strict=False)   -> str
slots_in(template)                        -> list[str]
missing_slots(template, values)           -> list[str]
```

## License

MIT
