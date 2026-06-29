"""Tests for deterministic instrument-identity resolution and the
context-anchored message placeholder."""

import unittest

import pytest
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage

from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    create_msg_delete,
    get_instrument_context_from_state,
)


@pytest.mark.unit
class BuildInstrumentContextTests(unittest.TestCase):
    def test_mentions_exact_symbol(self):
        context = build_instrument_context("TTF=F")
        self.assertIn("TTF=F", context)
        self.assertIn("futures suffix", context)
        self.assertNotIn("Resolved identity", context)

    def test_ngf_context_carries_henry_hub_identity(self):
        context = build_instrument_context("NG=F")
        self.assertIn("NG=F", context)
        self.assertIn("USD/MMBtu", context)
        self.assertIn("Henry Hub", context)
        self.assertIn("futures suffix", context)
        self.assertNotIn("EUR/MWh", context)

    def test_ttf_context_carries_eur_currency(self):
        context = build_instrument_context("TTF=F")
        self.assertIn("EUR/MWh", context)
        self.assertIn("Dutch TTF", context)

    def test_unknown_ticker_raises(self):
        # The app trades only gas contracts with profiles; an unknown ticker
        # (e.g. an equity) fails fast with KeyError rather than emitting a
        # misleading "commodity future, not a company" context.
        with self.assertRaises(KeyError):
            build_instrument_context("EC")


@pytest.mark.unit
class GetInstrumentContextFromStateTests(unittest.TestCase):
    def test_prefers_precomputed_context(self):
        state = {"company_of_interest": "TOTDY", "instrument_context": "PRECOMPUTED"}
        self.assertEqual(get_instrument_context_from_state(state), "PRECOMPUTED")

    def test_fallback_returns_ticker_only_context(self):
        # With no instrument_context, the fallback builds a ticker-only context.
        # build_instrument_context is pure string formatting (agent_utils no
        # longer imports yfinance), so this path is network-free by construction.
        context = get_instrument_context_from_state(
            {"company_of_interest": "TTF=F"}
        )
        self.assertIn("TTF=F", context)
        self.assertIn("futures suffix", context)


@pytest.mark.unit
class ContextAnchoredPlaceholderTests(unittest.TestCase):
    """#888 — the message-clear placeholder must not be a bare 'Continue'."""

    def _run(self, state_extra):
        state = {
            "messages": [
                HumanMessage(content="old", id="h1"),
                AIMessage(content="reply", id="a1"),
            ],
            **state_extra,
        }
        return create_msg_delete()(state)

    def test_placeholder_is_not_bare_continue(self):
        result = self._run(
            {"company_of_interest": "TTF=F", "trade_date": "2026-05-28"}
        )
        placeholder = result["messages"][-1]
        self.assertIsInstance(placeholder, HumanMessage)
        self.assertNotEqual(placeholder.content.strip(), "Continue")

    def test_placeholder_carries_resolved_identity(self):
        result = self._run(
            {
                "company_of_interest": "EC",
                "instrument_context": "The instrument to analyze is `EC`. Resolved identity: Company: Ecopetrol.",
                "trade_date": "2026-05-28",
            }
        )
        content = result["messages"][-1].content
        self.assertIn("Ecopetrol", content)
        self.assertIn("2026-05-28", content)

    def test_old_messages_are_removed(self):
        result = self._run({"company_of_interest": "TTF=F", "trade_date": "2026-05-28"})
        removals = [m for m in result["messages"] if isinstance(m, RemoveMessage)]
        humans = [m for m in result["messages"] if isinstance(m, HumanMessage)]
        self.assertEqual(len(removals), 2)
        self.assertEqual(len(humans), 1)

    def test_safe_defaults_when_state_minimal(self):
        result = create_msg_delete()({"messages": [], "company_of_interest": "TTF=F"})
        placeholder = result["messages"][-1]
        self.assertNotEqual(placeholder.content.strip(), "Continue")
        self.assertIn("TTF=F", placeholder.content)


if __name__ == "__main__":
    unittest.main()
