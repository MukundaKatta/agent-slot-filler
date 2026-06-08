"""Fill named {slot} placeholders in template strings for LLM agents.

Templates use single-brace syntax: ``{slot_name}``.  Literal braces can be
escaped by doubling them: ``{{`` renders as ``{`` and ``}}`` renders as ``}``.

Example::

    from agent_slot_filler import AgentSlotFiller

    filler = AgentSlotFiller()

    template = "Hello, {name}! You have {count} messages."
    result = filler.fill(template, {"name": "Alice", "count": "3"})
    # "Hello, Alice! You have 3 messages."

    # Partial fill — leave unfilled slots as-is
    partial = filler.fill_partial(template, {"name": "Bob"})
    # "Hello, Bob! You have {count} messages."

    # Introspect slots
    filler.slots_in(template)       # ["count", "name"]  (sorted)
    filler.missing_slots(template, {"name": "x"})  # ["count"]

    # Strict validation
    filler.validate(template, {"name": "x"})  # raises SlotError listing "count"
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator


class SlotError(Exception):
    """Raised when required slots are missing during fill/validate."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = sorted(missing)
        names = ", ".join(self.missing)
        super().__init__(f"Missing slots: {names}")


# Matches an escaped brace (``{{`` or ``}}``) OR a ``{slot}`` placeholder, in a
# single left-to-right pass.  Resolving escapes and slots together ensures that
# braces inside a substituted *value* are never mistaken for template escapes.
#
# This is the single source of truth for what counts as a slot: both the
# substitution methods (:meth:`fill`) and the inspection helpers
# (:meth:`slots_in`, :meth:`missing_slots`, ...) tokenize through it, so the
# slots reported are exactly the slots ``fill`` would substitute.  A naive
# ``{slot}`` regex with brace lookarounds disagrees on sequences like
# ``{{{name}}}`` (``{{`` + ``{name}`` + ``}}``), where the slot is adjacent to
# escaped braces.
_TOKEN_RE = re.compile(r"\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _iter_slots(template: str) -> Iterator[str]:
    """Yield slot names in *template* in left-to-right order.

    Uses the same tokenizer as :meth:`AgentSlotFiller.fill` so that escaped
    braces (``{{``/``}}``) are consumed before slot matching, guaranteeing the
    yielded names match exactly the slots that would be substituted.
    """
    for m in _TOKEN_RE.finditer(template):
        name = m.group(1)
        if name is not None:
            yield name


class AgentSlotFiller:
    """Fill named ``{slot}`` placeholders in template strings.

    Instances are stateless; all methods take the template and values as
    arguments so a single instance can be shared across calls.

    Args:
        default: Optional default value used for missing slots when
                 ``fill_partial`` is called.  When ``None`` (the default)
                 the original ``{slot}`` text is left in place.
        strict:  When ``True``, :meth:`fill` raises :class:`SlotError` for
                 any missing slot.  Defaults to ``False`` (silently leaves
                 slots unfilled).
    """

    def __init__(
        self,
        *,
        default: str | None = None,
        strict: bool = False,
    ) -> None:
        self._default = default
        self._strict = strict

    # ------------------------------------------------------------------
    # Core fill operations
    # ------------------------------------------------------------------

    def fill(
        self,
        template: str,
        values: dict[str, Any],
        *,
        strict: bool | None = None,
    ) -> str:
        """Return *template* with every ``{slot}`` replaced from *values*.

        Args:
            template: Template string containing ``{slot}`` placeholders.
            values:   Mapping of slot name → replacement value.
                      Values are converted to ``str`` via ``str()``.
            strict:   Override the instance-level ``strict`` flag for this
                      call.  When ``True``, raises :class:`SlotError` if any
                      slot has no value.  When ``False``, missing slots are
                      left as ``{slot}`` or replaced with the instance
                      ``default``.

        Returns:
            Filled string with escaped braces (``{{``, ``}}``) resolved to
            literal ``{`` and ``}``.
        """
        _strict = self._strict if strict is None else strict
        if _strict:
            missing = self.missing_slots(template, values)
            if missing:
                raise SlotError(missing)
        return self._replace_and_unescape(template, values)

    def fill_partial(
        self,
        template: str,
        values: dict[str, Any],
    ) -> str:
        """Return *template* with slots replaced where *values* provides them.

        Slots not present in *values* are left as ``{slot}`` in the output
        (or replaced with the instance ``default`` if set).  Escaped braces
        are NOT resolved so the result can be passed to :meth:`fill` again.

        Returns:
            Partially-filled template string.
        """
        return self._replace_slots(template, values, leave_missing=True)

    # ------------------------------------------------------------------
    # Inspection helpers
    # ------------------------------------------------------------------

    def slots_in(self, template: str) -> list[str]:
        """Return sorted list of unique slot names found in *template*."""
        return sorted(set(_iter_slots(template)))

    def missing_slots(
        self,
        template: str,
        values: dict[str, Any],
    ) -> list[str]:
        """Return sorted list of slot names in *template* not in *values*."""
        keys = set(values.keys())
        return sorted({name for name in _iter_slots(template) if name not in keys})

    def filled_slots(
        self,
        template: str,
        values: dict[str, Any],
    ) -> list[str]:
        """Return sorted list of slot names in *template* that *values* covers."""
        keys = set(values.keys())
        return sorted({name for name in _iter_slots(template) if name in keys})

    def validate(
        self,
        template: str,
        values: dict[str, Any],
    ) -> None:
        """Raise :class:`SlotError` if any slot in *template* is missing.

        Args:
            template: Template string.
            values:   Mapping of available slot values.

        Raises:
            SlotError: With the sorted list of missing slot names.
        """
        missing = self.missing_slots(template, values)
        if missing:
            raise SlotError(missing)

    def is_complete(
        self,
        template: str,
        values: dict[str, Any],
    ) -> bool:
        """Return ``True`` if *values* covers every slot in *template*."""
        return len(self.missing_slots(template, values)) == 0

    def slot_count(self, template: str) -> int:
        """Return the number of unique slots in *template*."""
        return len(self.slots_in(template))

    def has_slots(self, template: str) -> bool:
        """Return ``True`` if *template* contains at least one slot."""
        return next(_iter_slots(template), None) is not None

    # ------------------------------------------------------------------
    # Multi-template helpers
    # ------------------------------------------------------------------

    def fill_many(
        self,
        templates: list[str],
        values: dict[str, Any],
        *,
        strict: bool | None = None,
    ) -> list[str]:
        """Fill each template in *templates* with *values*.

        Returns:
            List of filled strings in the same order as *templates*.
        """
        return [self.fill(t, values, strict=strict) for t in templates]

    def fill_dict(
        self,
        templates: dict[str, str],
        values: dict[str, Any],
        *,
        strict: bool | None = None,
    ) -> dict[str, str]:
        """Fill each value in a ``{key: template}`` dict.

        Returns:
            New dict with the same keys, filled values.
        """
        return {k: self.fill(v, values, strict=strict) for k, v in templates.items()}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _slot_value(self, name: str, values: dict[str, Any]) -> str | None:
        """Resolve a slot's replacement, or ``None`` to leave it in place.

        Returns the stringified value when present, the instance ``default``
        when set, or ``None`` when the slot should be left as ``{slot}``.
        """
        if name in values:
            return str(values[name])
        if self._default is not None:
            return self._default
        return None

    def _replace_slots(
        self,
        template: str,
        values: dict[str, Any],
        *,
        leave_missing: bool,
    ) -> str:
        """Replace ``{slot}`` occurrences without resolving escaped braces.

        Used by :meth:`fill_partial` so the result remains a valid template
        (``{{``/``}}`` escapes are preserved) that can be filled again.  Tokens
        are matched left-to-right with the same tokenizer as :meth:`fill`, so an
        escaped brace adjacent to a slot (e.g. ``{{{name}}}``) is recognized
        identically — but escapes themselves are emitted verbatim.
        """

        def replacer(m: re.Match[str]) -> str:
            name = m.group(1)
            if name is None:
                return m.group(0)  # escaped brace ({{ or }}) — leave untouched
            value = self._slot_value(name, values)
            if value is not None:
                return value
            if leave_missing:
                return m.group(0)  # keep original {slot}
            return ""

        return _TOKEN_RE.sub(replacer, template)

    def _replace_and_unescape(
        self,
        template: str,
        values: dict[str, Any],
    ) -> str:
        """Replace ``{slot}`` placeholders and resolve ``{{``/``}}`` escapes.

        Performed in a single left-to-right pass so that braces appearing in a
        substituted *value* are emitted verbatim and never re-interpreted as
        template escapes.
        """

        def replacer(m: re.Match[str]) -> str:
            token = m.group(0)
            if token == "{{":
                return "{"
            if token == "}}":
                return "}"
            name = m.group(1)
            value = self._slot_value(name, values)
            if value is not None:
                return value
            return token  # keep original {slot}

        return _TOKEN_RE.sub(replacer, template)

    # ------------------------------------------------------------------
    # Module-level convenience functions (also available on the instance)
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"AgentSlotFiller(strict={self._strict!r}, default={self._default!r})"


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


def fill(template: str, values: dict[str, Any], *, strict: bool = False) -> str:
    """Fill *template* using *values*.  Module-level shorthand."""
    return AgentSlotFiller(strict=strict).fill(template, values)


def slots_in(template: str) -> list[str]:
    """Return sorted unique slot names in *template*.  Module-level shorthand."""
    return AgentSlotFiller().slots_in(template)


def missing_slots(template: str, values: dict[str, Any]) -> list[str]:
    """Return missing slot names.  Module-level shorthand."""
    return AgentSlotFiller().missing_slots(template, values)
