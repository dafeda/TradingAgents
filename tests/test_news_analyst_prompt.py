"""Guard the news analyst prompt against tool-signature drift (#1116).

The prompt used to advertise ``get_news(query, ...)`` while the tool takes a
``ticker``, tricking the LLM into hallucinating free-text query calls.
"""
import inspect

import pytest

import tradingagents.agents.analysts.news_analyst as na
from tradingagents.agents.utils.news_data_tools import get_news


@pytest.mark.unit
def test_get_news_takes_ticker_not_query():
    arg_names = set(get_news.args.keys())
    assert "ticker" in arg_names
    assert "query" not in arg_names


@pytest.mark.unit
def test_news_prompt_matches_get_news_signature():
    src = inspect.getsource(na)
    assert "get_news(ticker, start_date, end_date)" in src
    assert "get_news(query" not in src


@pytest.mark.unit
def test_news_prompt_forbids_process_narration():
    src = inspect.getsource(na)
    assert "Begin the final report directly with decision-relevant analysis" in src
    assert "Do not include process narration" in src
    assert "All data gathered" in src
    assert "I now have a complete picture" in src


@pytest.mark.unit
def test_news_prompt_requires_grounded_inline_citations():
    src = inspect.getsource(na)
    assert "inline Markdown citation immediately after the claim" in src
    assert "Include these citations in table cells too" in src
    assert "Use only source URLs returned by the tools" in src
    assert "never invent, guess, or alter a URL" in src
