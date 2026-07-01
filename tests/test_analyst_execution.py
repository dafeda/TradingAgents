import unittest

from tradingagents.analyst_type import AnalystType
from tradingagents.graph.analyst_execution import (
    AnalystWallTimeTracker,
    build_analyst_execution_plan,
    get_initial_analyst_node,
    sync_analyst_tracker_from_chunk,
)


class AnalystExecutionPlanTests(unittest.TestCase):
    def test_build_plan_preserves_selected_order(self):
        plan = build_analyst_execution_plan([AnalystType.NEWS, AnalystType.MARKET])

        self.assertEqual([spec.key for spec in plan.specs], [AnalystType.NEWS, AnalystType.MARKET])
        self.assertEqual(plan.specs[0].agent_node, "News Analyst")
        self.assertEqual(plan.specs[0].tool_node, "tools_news")
        self.assertEqual(plan.specs[0].clear_node, "Msg Clear News")

    def test_rejects_unknown_analyst_keys(self):
        with self.assertRaises(ValueError):
            build_analyst_execution_plan(["market", "macro"])

    def test_get_initial_analyst_node_uses_plan_metadata(self):
        plan = build_analyst_execution_plan([AnalystType.FUNDAMENTALS, AnalystType.NEWS])

        self.assertEqual(
            get_initial_analyst_node(plan),
            "Fundamentals Analyst",
        )

    def test_social_key_displays_as_sentiment_analyst(self):
        # The wire key stays "social" for saved-config back-compat, but the
        # user-visible agent_node label must match the v0.2.5 rename so the
        # wall-time summary and any future consumer of agent_node says
        # "Sentiment Analyst" rather than the legacy "Social Analyst".
        plan = build_analyst_execution_plan([AnalystType.SOCIAL])
        spec = plan.specs[0]
        self.assertEqual(spec.key, AnalystType.SOCIAL)
        self.assertEqual(spec.agent_node, "Sentiment Analyst")
        self.assertEqual(spec.report_key, "sentiment_report")


class AnalystWallTimeTrackerTests(unittest.TestCase):
    def test_records_wall_time_when_analyst_completes(self):
        plan = build_analyst_execution_plan([AnalystType.MARKET, AnalystType.NEWS])
        tracker = AnalystWallTimeTracker(plan)

        tracker.mark_started(AnalystType.MARKET, started_at=10.0)
        tracker.mark_completed(AnalystType.MARKET, completed_at=13.5)

        self.assertEqual(tracker.get_wall_times(), {AnalystType.MARKET: 3.5})

    def test_formats_summary_in_plan_order(self):
        plan = build_analyst_execution_plan([AnalystType.NEWS, AnalystType.MARKET])
        tracker = AnalystWallTimeTracker(plan)

        tracker.mark_started(AnalystType.MARKET, started_at=20.0)
        tracker.mark_completed(AnalystType.MARKET, completed_at=22.25)
        tracker.mark_started(AnalystType.NEWS, started_at=10.0)
        tracker.mark_completed(AnalystType.NEWS, completed_at=14.0)

        self.assertEqual(
            tracker.format_summary(),
            "Analyst wall time: News 4.00s | Market 2.25s",
        )

    def test_syncs_wall_time_from_sequential_chunks(self):
        plan = build_analyst_execution_plan([AnalystType.MARKET, AnalystType.NEWS])
        tracker = AnalystWallTimeTracker(plan)

        sync_analyst_tracker_from_chunk(tracker, {}, now=10.0)
        self.assertEqual(tracker.get_wall_times(), {})

        sync_analyst_tracker_from_chunk(
            tracker,
            {"market_report": "done"},
            now=13.0,
        )
        self.assertEqual(tracker.get_wall_times(), {AnalystType.MARKET: 3.0})

        sync_analyst_tracker_from_chunk(
            tracker,
            {"market_report": "done", "news_report": "done"},
            now=18.0,
        )
        self.assertEqual(
            tracker.get_wall_times(),
            {AnalystType.MARKET: 3.0, AnalystType.NEWS: 5.0},
        )
