"""Tests for metric display formatting."""

from __future__ import annotations

from dashboard_rca.formatting import format_metric_value


def test_format_gdp_on_hundred_scale() -> None:
    assert format_metric_value("Index_GDP", 22.3, lang="FR") == "22.3 sur 100"


def test_format_index_with_hundred_scale() -> None:
    assert format_metric_value("Index_health", 72.3, lang="EN") == "72.3 of 100"


def test_format_missing_value() -> None:
    assert format_metric_value("Index_GDP", None) == "—"
