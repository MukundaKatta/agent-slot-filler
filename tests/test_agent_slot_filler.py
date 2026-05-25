"""Tests for agent_slot_filler."""

from __future__ import annotations

import pytest

from agent_slot_filler import AgentSlotFiller, SlotError
from agent_slot_filler.core import fill, missing_slots, slots_in

# ---------------------------------------------------------------------------
# Constructor / repr
# ---------------------------------------------------------------------------


def test_default_instance():
    f = AgentSlotFiller()
    assert repr(f) == "AgentSlotFiller(strict=False, default=None)"


def test_strict_instance():
    f = AgentSlotFiller(strict=True)
    assert "strict=True" in repr(f)


def test_default_value_instance():
    f = AgentSlotFiller(default="N/A")
    assert "default='N/A'" in repr(f)


# ---------------------------------------------------------------------------
# fill — basic
# ---------------------------------------------------------------------------


def test_fill_single_slot():
    f = AgentSlotFiller()
    assert f.fill("Hello, {name}!", {"name": "Alice"}) == "Hello, Alice!"


def test_fill_multiple_slots():
    f = AgentSlotFiller()
    result = f.fill("{greeting}, {name}!", {"greeting": "Hi", "name": "Bob"})
    assert result == "Hi, Bob!"


def test_fill_repeated_slot():
    f = AgentSlotFiller()
    assert f.fill("{x} and {x}", {"x": "foo"}) == "foo and foo"


def test_fill_int_value():
    f = AgentSlotFiller()
    assert f.fill("count={n}", {"n": 42}) == "count=42"


def test_fill_float_value():
    f = AgentSlotFiller()
    assert f.fill("v={v}", {"v": 3.14}) == "v=3.14"


def test_fill_no_slots():
    f = AgentSlotFiller()
    assert f.fill("no slots here", {}) == "no slots here"


def test_fill_empty_template():
    f = AgentSlotFiller()
    assert f.fill("", {"x": "y"}) == ""


def test_fill_extra_values_ignored():
    f = AgentSlotFiller()
    assert f.fill("Hi {name}", {"name": "X", "extra": "ignored"}) == "Hi X"


def test_fill_missing_slot_leaves_placeholder():
    f = AgentSlotFiller()
    assert f.fill("Hello {name}", {}) == "Hello {name}"


def test_fill_escaped_braces():
    f = AgentSlotFiller()
    assert f.fill("{{literal}}", {}) == "{literal}"


def test_fill_escaped_and_slot():
    f = AgentSlotFiller()
    assert f.fill("{{name}} is {name}", {"name": "Alice"}) == "{name} is Alice"


def test_fill_double_escaped():
    f = AgentSlotFiller()
    assert f.fill("{{{{x}}}}", {}) == "{{x}}"


# ---------------------------------------------------------------------------
# fill — strict mode
# ---------------------------------------------------------------------------


def test_fill_strict_raises_on_missing():
    f = AgentSlotFiller(strict=True)
    with pytest.raises(SlotError) as exc:
        f.fill("{a} {b}", {"a": "1"})
    assert "b" in exc.value.missing


def test_fill_strict_ok_when_complete():
    f = AgentSlotFiller(strict=True)
    assert f.fill("{a}", {"a": "ok"}) == "ok"


def test_fill_strict_override_per_call():
    f = AgentSlotFiller(strict=False)
    with pytest.raises(SlotError):
        f.fill("{missing}", {}, strict=True)


def test_fill_non_strict_override_per_call():
    f = AgentSlotFiller(strict=True)
    # strict=False per-call should NOT raise
    result = f.fill("{missing}", {}, strict=False)
    assert result == "{missing}"


# ---------------------------------------------------------------------------
# fill — default value
# ---------------------------------------------------------------------------


def test_fill_default_replaces_missing():
    f = AgentSlotFiller(default="???")
    assert f.fill("{x} {y}", {"x": "ok"}) == "ok ???"


def test_fill_default_empty_string():
    f = AgentSlotFiller(default="")
    assert f.fill("a{b}c", {}) == "ac"


# ---------------------------------------------------------------------------
# fill_partial
# ---------------------------------------------------------------------------


def test_fill_partial_leaves_unfilled():
    f = AgentSlotFiller()
    result = f.fill_partial("Hello {name}, {greeting}!", {"name": "Bob"})
    assert result == "Hello Bob, {greeting}!"


def test_fill_partial_all_provided():
    f = AgentSlotFiller()
    result = f.fill_partial("{a} {b}", {"a": "1", "b": "2"})
    assert result == "1 2"


def test_fill_partial_none_provided():
    f = AgentSlotFiller()
    result = f.fill_partial("{a} {b}", {})
    assert result == "{a} {b}"


def test_fill_partial_escaped_braces_stay():
    f = AgentSlotFiller()
    # escaped braces are NOT resolved in fill_partial so result can be re-filled
    result = f.fill_partial("{{escaped}} {slot}", {"slot": "X"})
    assert "{{escaped}}" in result
    assert "X" in result


# ---------------------------------------------------------------------------
# slots_in
# ---------------------------------------------------------------------------


def test_slots_in_sorted():
    f = AgentSlotFiller()
    assert f.slots_in("{z} {a} {m}") == ["a", "m", "z"]


def test_slots_in_deduped():
    f = AgentSlotFiller()
    assert f.slots_in("{x} {x} {x}") == ["x"]


def test_slots_in_no_slots():
    f = AgentSlotFiller()
    assert f.slots_in("no slots") == []


def test_slots_in_ignores_escaped():
    f = AgentSlotFiller()
    assert f.slots_in("{{not_a_slot}} {real}") == ["real"]


def test_slots_in_underscore_names():
    f = AgentSlotFiller()
    assert f.slots_in("{user_name} {_private}") == ["_private", "user_name"]


# ---------------------------------------------------------------------------
# missing_slots
# ---------------------------------------------------------------------------


def test_missing_slots_all_present():
    f = AgentSlotFiller()
    assert f.missing_slots("{a} {b}", {"a": 1, "b": 2}) == []


def test_missing_slots_some_missing():
    f = AgentSlotFiller()
    result = f.missing_slots("{a} {b} {c}", {"a": 1})
    assert result == ["b", "c"]


def test_missing_slots_all_missing():
    f = AgentSlotFiller()
    assert f.missing_slots("{x} {y}", {}) == ["x", "y"]


def test_missing_slots_sorted():
    f = AgentSlotFiller()
    assert f.missing_slots("{z} {a}", {}) == ["a", "z"]


# ---------------------------------------------------------------------------
# filled_slots
# ---------------------------------------------------------------------------


def test_filled_slots():
    f = AgentSlotFiller()
    assert f.filled_slots("{a} {b} {c}", {"a": 1, "c": 3}) == ["a", "c"]


def test_filled_slots_none():
    f = AgentSlotFiller()
    assert f.filled_slots("{a}", {}) == []


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def test_validate_ok():
    f = AgentSlotFiller()
    f.validate("{x}", {"x": "ok"})  # no raise


def test_validate_raises():
    f = AgentSlotFiller()
    with pytest.raises(SlotError) as exc:
        f.validate("{a} {b}", {"a": "1"})
    assert exc.value.missing == ["b"]


def test_validate_multiple_missing():
    f = AgentSlotFiller()
    with pytest.raises(SlotError) as exc:
        f.validate("{x} {y} {z}", {})
    assert exc.value.missing == ["x", "y", "z"]


def test_slot_error_message():
    err = SlotError(["z", "a"])
    assert "a" in str(err)
    assert "z" in str(err)
    assert err.missing == ["a", "z"]  # sorted


# ---------------------------------------------------------------------------
# is_complete / has_slots / slot_count
# ---------------------------------------------------------------------------


def test_is_complete_true():
    f = AgentSlotFiller()
    assert f.is_complete("{a} {b}", {"a": 1, "b": 2}) is True


def test_is_complete_false():
    f = AgentSlotFiller()
    assert f.is_complete("{a} {b}", {"a": 1}) is False


def test_has_slots_true():
    f = AgentSlotFiller()
    assert f.has_slots("{x}") is True


def test_has_slots_false():
    f = AgentSlotFiller()
    assert f.has_slots("plain text") is False


def test_slot_count():
    f = AgentSlotFiller()
    assert f.slot_count("{a} {b} {a}") == 2  # unique


# ---------------------------------------------------------------------------
# fill_many / fill_dict
# ---------------------------------------------------------------------------


def test_fill_many():
    f = AgentSlotFiller()
    results = f.fill_many(["{x}", "val={x}"], {"x": "hi"})
    assert results == ["hi", "val=hi"]


def test_fill_many_empty():
    f = AgentSlotFiller()
    assert f.fill_many([], {"x": "y"}) == []


def test_fill_dict():
    f = AgentSlotFiller()
    out = f.fill_dict({"k1": "{a}", "k2": "{b}"}, {"a": "1", "b": "2"})
    assert out == {"k1": "1", "k2": "2"}


def test_fill_dict_preserves_keys():
    f = AgentSlotFiller()
    out = f.fill_dict({"hello": "world"}, {})
    assert out == {"hello": "world"}


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


def test_module_fill():
    assert fill("{x}", {"x": "ok"}) == "ok"


def test_module_slots_in():
    assert slots_in("{b} {a}") == ["a", "b"]


def test_module_missing_slots():
    assert missing_slots("{a} {b}", {"a": 1}) == ["b"]


def test_module_fill_strict():
    with pytest.raises(SlotError):
        fill("{missing}", {}, strict=True)
