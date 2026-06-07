"""Tests for agent_slot_filler.

Uses only the Python standard library (``unittest``) so the suite runs with::

    python -m unittest discover -s tests

without any third-party dependencies.
"""

from __future__ import annotations

import os
import sys
import unittest

# Make the ``src/`` layout importable when the suite is run without first
# installing the package (e.g. ``python -m unittest discover -s tests``).
# No-op once the package is installed / already importable.
_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import agent_slot_filler
from agent_slot_filler import AgentSlotFiller, SlotError
from agent_slot_filler.core import fill, missing_slots, slots_in


class ConstructorReprTests(unittest.TestCase):
    def test_default_instance(self):
        f = AgentSlotFiller()
        self.assertEqual(repr(f), "AgentSlotFiller(strict=False, default=None)")

    def test_strict_instance(self):
        f = AgentSlotFiller(strict=True)
        self.assertIn("strict=True", repr(f))

    def test_default_value_instance(self):
        f = AgentSlotFiller(default="N/A")
        self.assertIn("default='N/A'", repr(f))


class FillBasicTests(unittest.TestCase):
    def setUp(self):
        self.f = AgentSlotFiller()

    def test_fill_single_slot(self):
        self.assertEqual(self.f.fill("Hello, {name}!", {"name": "Alice"}), "Hello, Alice!")

    def test_fill_multiple_slots(self):
        result = self.f.fill("{greeting}, {name}!", {"greeting": "Hi", "name": "Bob"})
        self.assertEqual(result, "Hi, Bob!")

    def test_fill_repeated_slot(self):
        self.assertEqual(self.f.fill("{x} and {x}", {"x": "foo"}), "foo and foo")

    def test_fill_adjacent_slots(self):
        self.assertEqual(self.f.fill("{a}{b}", {"a": "1", "b": "2"}), "12")

    def test_fill_int_value(self):
        self.assertEqual(self.f.fill("count={n}", {"n": 42}), "count=42")

    def test_fill_float_value(self):
        self.assertEqual(self.f.fill("v={v}", {"v": 3.14}), "v=3.14")

    def test_fill_none_value_stringified(self):
        self.assertEqual(self.f.fill("x={v}", {"v": None}), "x=None")

    def test_fill_no_slots(self):
        self.assertEqual(self.f.fill("no slots here", {}), "no slots here")

    def test_fill_empty_template(self):
        self.assertEqual(self.f.fill("", {"x": "y"}), "")

    def test_fill_extra_values_ignored(self):
        self.assertEqual(self.f.fill("Hi {name}", {"name": "X", "extra": "ignored"}), "Hi X")

    def test_fill_missing_slot_leaves_placeholder(self):
        self.assertEqual(self.f.fill("Hello {name}", {}), "Hello {name}")


class FillEscapeTests(unittest.TestCase):
    def setUp(self):
        self.f = AgentSlotFiller()

    def test_fill_escaped_braces(self):
        self.assertEqual(self.f.fill("{{literal}}", {}), "{literal}")

    def test_fill_escaped_and_slot(self):
        self.assertEqual(
            self.f.fill("{{name}} is {name}", {"name": "Alice"}), "{name} is Alice"
        )

    def test_fill_double_escaped(self):
        self.assertEqual(self.f.fill("{{{{x}}}}", {}), "{{x}}")

    def test_fill_triple_brace_resolves_slot(self):
        # {{ + {x} + }} -> "{" + value + "}"
        self.assertEqual(self.f.fill("{{{x}}}", {"x": "V"}), "{V}")

    def test_fill_value_with_double_braces_preserved(self):
        # A value containing {{ or }} must NOT be re-interpreted as a template
        # escape — substituted braces are emitted verbatim.
        self.assertEqual(self.f.fill("{x}", {"x": "{{weird}}"}), "{{weird}}")

    def test_fill_value_with_single_braces_preserved(self):
        self.assertEqual(self.f.fill("[{x}]", {"x": "{y}"}), "[{y}]")

    def test_fill_default_value_with_braces_preserved(self):
        f = AgentSlotFiller(default="{{NA}}")
        self.assertEqual(f.fill("{missing}", {}), "{{NA}}")

    def test_fill_escape_around_slot(self):
        self.assertEqual(self.f.fill("{{ {name} }}", {"name": "X"}), "{ X }")


class FillStrictTests(unittest.TestCase):
    def test_fill_strict_raises_on_missing(self):
        f = AgentSlotFiller(strict=True)
        with self.assertRaises(SlotError) as ctx:
            f.fill("{a} {b}", {"a": "1"})
        self.assertIn("b", ctx.exception.missing)

    def test_fill_strict_ok_when_complete(self):
        f = AgentSlotFiller(strict=True)
        self.assertEqual(f.fill("{a}", {"a": "ok"}), "ok")

    def test_fill_strict_override_per_call(self):
        f = AgentSlotFiller(strict=False)
        with self.assertRaises(SlotError):
            f.fill("{missing}", {}, strict=True)

    def test_fill_non_strict_override_per_call(self):
        f = AgentSlotFiller(strict=True)
        # strict=False per-call should NOT raise
        self.assertEqual(f.fill("{missing}", {}, strict=False), "{missing}")


class FillDefaultTests(unittest.TestCase):
    def test_fill_default_replaces_missing(self):
        f = AgentSlotFiller(default="???")
        self.assertEqual(f.fill("{x} {y}", {"x": "ok"}), "ok ???")

    def test_fill_default_empty_string(self):
        f = AgentSlotFiller(default="")
        self.assertEqual(f.fill("a{b}c", {}), "ac")


class FillPartialTests(unittest.TestCase):
    def setUp(self):
        self.f = AgentSlotFiller()

    def test_fill_partial_leaves_unfilled(self):
        result = self.f.fill_partial("Hello {name}, {greeting}!", {"name": "Bob"})
        self.assertEqual(result, "Hello Bob, {greeting}!")

    def test_fill_partial_all_provided(self):
        self.assertEqual(self.f.fill_partial("{a} {b}", {"a": "1", "b": "2"}), "1 2")

    def test_fill_partial_none_provided(self):
        self.assertEqual(self.f.fill_partial("{a} {b}", {}), "{a} {b}")

    def test_fill_partial_escaped_braces_stay(self):
        # escaped braces are NOT resolved in fill_partial so result can be re-filled
        result = self.f.fill_partial("{{escaped}} {slot}", {"slot": "X"})
        self.assertIn("{{escaped}}", result)
        self.assertIn("X", result)

    def test_fill_partial_with_default(self):
        f = AgentSlotFiller(default="-")
        self.assertEqual(f.fill_partial("{a} {b}", {"a": "1"}), "1 -")

    def test_fill_partial_then_fill_round_trip(self):
        # Two-pass filling: partial leaves escapes + unfilled slots, final fill
        # resolves everything exactly once.
        partial = self.f.fill_partial("{{literal}} {a} {b}", {"a": "1"})
        self.assertEqual(partial, "{{literal}} 1 {b}")
        self.assertEqual(self.f.fill(partial, {"b": "2"}), "{literal} 1 2")


class SlotsInTests(unittest.TestCase):
    def setUp(self):
        self.f = AgentSlotFiller()

    def test_slots_in_sorted(self):
        self.assertEqual(self.f.slots_in("{z} {a} {m}"), ["a", "m", "z"])

    def test_slots_in_deduped(self):
        self.assertEqual(self.f.slots_in("{x} {x} {x}"), ["x"])

    def test_slots_in_no_slots(self):
        self.assertEqual(self.f.slots_in("no slots"), [])

    def test_slots_in_ignores_escaped(self):
        self.assertEqual(self.f.slots_in("{{not_a_slot}} {real}"), ["real"])

    def test_slots_in_underscore_names(self):
        self.assertEqual(self.f.slots_in("{user_name} {_private}"), ["_private", "user_name"])

    def test_slots_in_rejects_leading_digit(self):
        # Slot names must be identifiers; a leading digit is not a valid slot.
        self.assertEqual(self.f.slots_in("{1bad}"), [])


class MissingSlotsTests(unittest.TestCase):
    def setUp(self):
        self.f = AgentSlotFiller()

    def test_missing_slots_all_present(self):
        self.assertEqual(self.f.missing_slots("{a} {b}", {"a": 1, "b": 2}), [])

    def test_missing_slots_some_missing(self):
        self.assertEqual(self.f.missing_slots("{a} {b} {c}", {"a": 1}), ["b", "c"])

    def test_missing_slots_all_missing(self):
        self.assertEqual(self.f.missing_slots("{x} {y}", {}), ["x", "y"])

    def test_missing_slots_sorted(self):
        self.assertEqual(self.f.missing_slots("{z} {a}", {}), ["a", "z"])


class FilledSlotsTests(unittest.TestCase):
    def setUp(self):
        self.f = AgentSlotFiller()

    def test_filled_slots(self):
        self.assertEqual(self.f.filled_slots("{a} {b} {c}", {"a": 1, "c": 3}), ["a", "c"])

    def test_filled_slots_none(self):
        self.assertEqual(self.f.filled_slots("{a}", {}), [])


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self.f = AgentSlotFiller()

    def test_validate_ok(self):
        self.assertIsNone(self.f.validate("{x}", {"x": "ok"}))

    def test_validate_raises(self):
        with self.assertRaises(SlotError) as ctx:
            self.f.validate("{a} {b}", {"a": "1"})
        self.assertEqual(ctx.exception.missing, ["b"])

    def test_validate_multiple_missing(self):
        with self.assertRaises(SlotError) as ctx:
            self.f.validate("{x} {y} {z}", {})
        self.assertEqual(ctx.exception.missing, ["x", "y", "z"])

    def test_slot_error_message(self):
        err = SlotError(["z", "a"])
        self.assertIn("a", str(err))
        self.assertIn("z", str(err))
        self.assertEqual(err.missing, ["a", "z"])  # sorted

    def test_slot_error_is_exception(self):
        self.assertIsInstance(SlotError(["x"]), Exception)


class GuardHelperTests(unittest.TestCase):
    def setUp(self):
        self.f = AgentSlotFiller()

    def test_is_complete_true(self):
        self.assertIs(self.f.is_complete("{a} {b}", {"a": 1, "b": 2}), True)

    def test_is_complete_false(self):
        self.assertIs(self.f.is_complete("{a} {b}", {"a": 1}), False)

    def test_has_slots_true(self):
        self.assertIs(self.f.has_slots("{x}"), True)

    def test_has_slots_false(self):
        self.assertIs(self.f.has_slots("plain text"), False)

    def test_has_slots_ignores_escaped(self):
        self.assertIs(self.f.has_slots("{{escaped}}"), False)

    def test_slot_count(self):
        self.assertEqual(self.f.slot_count("{a} {b} {a}"), 2)  # unique


class MultiTemplateTests(unittest.TestCase):
    def setUp(self):
        self.f = AgentSlotFiller()

    def test_fill_many(self):
        self.assertEqual(self.f.fill_many(["{x}", "val={x}"], {"x": "hi"}), ["hi", "val=hi"])

    def test_fill_many_empty(self):
        self.assertEqual(self.f.fill_many([], {"x": "y"}), [])

    def test_fill_dict(self):
        out = self.f.fill_dict({"k1": "{a}", "k2": "{b}"}, {"a": "1", "b": "2"})
        self.assertEqual(out, {"k1": "1", "k2": "2"})

    def test_fill_dict_preserves_keys(self):
        self.assertEqual(self.f.fill_dict({"hello": "world"}, {}), {"hello": "world"})

    def test_fill_many_strict_raises(self):
        with self.assertRaises(SlotError):
            self.f.fill_many(["{a}", "{b}"], {"a": "1"}, strict=True)

    def test_fill_dict_strict_raises(self):
        with self.assertRaises(SlotError):
            self.f.fill_dict({"k": "{missing}"}, {}, strict=True)


class ModuleLevelTests(unittest.TestCase):
    def test_module_fill(self):
        self.assertEqual(fill("{x}", {"x": "ok"}), "ok")

    def test_module_slots_in(self):
        self.assertEqual(slots_in("{b} {a}"), ["a", "b"])

    def test_module_missing_slots(self):
        self.assertEqual(missing_slots("{a} {b}", {"a": 1}), ["b"])

    def test_module_fill_strict(self):
        with self.assertRaises(SlotError):
            fill("{missing}", {}, strict=True)

    def test_top_level_exports(self):
        # The convenience functions and classes documented in the README must be
        # importable directly from the package, not only from .core.
        for name in ("AgentSlotFiller", "SlotError", "fill", "slots_in", "missing_slots"):
            self.assertTrue(hasattr(agent_slot_filler, name), name)
            self.assertIn(name, agent_slot_filler.__all__)

    def test_top_level_fill_matches_core(self):
        self.assertEqual(
            agent_slot_filler.fill("{a}", {"a": "1"}), fill("{a}", {"a": "1"})
        )


if __name__ == "__main__":
    unittest.main()
