"""Fill named {slot} placeholders in template strings for LLM agents."""

from __future__ import annotations

from agent_slot_filler.core import (
    AgentSlotFiller,
    SlotError,
    fill,
    missing_slots,
    slots_in,
)

__all__ = [
    "AgentSlotFiller",
    "SlotError",
    "fill",
    "missing_slots",
    "slots_in",
]
__version__ = "0.1.0"
