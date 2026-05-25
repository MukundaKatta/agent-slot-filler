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
from typing import Any


class SlotError(Exception):
    """Raised when required slots are missing during fill/validate."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = sorted(missing)
        names = ", ".join(self.missing)
        super().__init__(f"Missing slots: {names}")


# Matches {slot_name} — slot names are identifiers (letters, digits, _).
# Negative lookbehind/lookahead skip {{ ... }} escaped-brace sequences.
_SLOT_RE = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})")


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
        result = self._replace_slots(template, values, leave_missing=True)
        return self._unescape(result)

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
        return sorted({m.group(1) for m in _SLOT_RE.finditer(template)})

    def missing_slots(
        self,
        template: str,
        values: dict[str, Any],
    ) -> list[str]:
        """Return sorted list of slot names in *template* not in *values*."""
        keys = set(values.keys())
        return sorted(
            {m.group(1) for m in _SLOT_RE.finditer(template) if m.group(1) not in keys}
        )

    def filled_slots(
        self,
        template: str,
        values: dict[str, Any],
    ) -> list[str]:
        """Return sorted list of slot names in *template* that *values* covers."""
        keys = set(values.keys())
        return sorted(
            {m.group(1) for m in _SLOT_RE.finditer(template) if m.group(1) in keys}
        )

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
        return bool(_SLOT_RE.search(template))

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

    def _replace_slots(
        self,
        template: str,
        values: dict[str, Any],
        *,
        leave_missing: bool,
    ) -> str:
        """Replace ``{slot}`` occurrences; optionally leave missing ones."""

        def replacer(m: re.Match[str]) -> str:
            name = m.group(1)
            if name in values:
                return str(values[name])
            if self._default is not None:
                return self._default
            if leave_missing:
                return m.group(0)  # keep original {slot}
            return ""

        return _SLOT_RE.sub(replacer, template)

    @staticmethod
    def _unescape(text: str) -> str:
        """Convert ``{{`` → ``{`` and ``}}`` → ``}``."""
        return text.replace("{{", "{").replace("}}", "}")

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
