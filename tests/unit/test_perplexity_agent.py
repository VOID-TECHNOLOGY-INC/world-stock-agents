from __future__ import annotations

import os
from unittest.mock import patch, MagicMock
from datetime import date

import pytest

from src.agents.perplexity_agent import (
    is_perplexity_configured,
    generate_thesis_and_risks,
)
from src.agents.regions import RegionAgent


def test_is_perplexity_configured(monkeypatch):
    monkeypatch.delenv("PPLX_API_KEY", raising=False)
    assert not is_perplexity_configured()
    monkeypatch.setenv("PPLX_API_KEY", "dummy")
    assert is_perplexity_configured()


@patch("src.agents.perplexity_agent.requests.post")
def test_generate_thesis_and_risks(mock_post, monkeypatch):
    monkeypatch.setenv("PPLX_API_KEY", "dummy")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "サンプルthesis\n- risk1\n- risk2"}}]
    }
    mock_resp.raise_for_status = lambda: None
    mock_post.return_value = mock_resp
    thesis, risks = generate_thesis_and_risks(
        "TEST", "Test Corp", "US", {"fundamental": 0.5}, {}
    )
    assert "thesis" in thesis or "サンプル" in thesis
    assert risks == ["risk1", "risk2"]


@patch("src.agents.regions.load_universe")
@patch("src.agents.regions.is_openai_configured", return_value=False)
@patch("src.agents.regions.is_perplexity_configured", return_value=True)
@patch("src.agents.regions.generate_thesis_and_risks_perplexity")
def test_region_agent_uses_perplexity(
    mock_generate, mock_pplx_cfg, mock_openai_cfg, mock_load
):
    mock_generate.return_value = ("Test thesis", ["Risk1", "Risk2"])
    mock_load.side_effect = Exception("fallback")
    agent = RegionAgent("TEST", "dummy", {})
    result = agent.run(date(2025, 8, 15), top_n=1)
    assert mock_generate.called
    assert result["candidates"][0]["thesis"] == "Test thesis"


@patch("src.agents.perplexity_agent.requests.post")
def test_generate_thesis_and_risks_json_parsing(mock_post, monkeypatch):
    """JSONで返ってきたときに堅牢にパースできること。"""
    monkeypatch.setenv("PPLX_API_KEY", "dummy")
    content = (
        '{"thesis":"短期の成長余地あり","risks":["需給悪化","規制"],'
        '"references":[{"url":"https://example.com","title":"news"}]}'
    )
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    mock_resp.raise_for_status = lambda: None
    mock_post.return_value = mock_resp

    thesis, risks = generate_thesis_and_risks(
        "TEST", "Test Corp", "US",
        {"fundamental": 0.7, "growth": 0.6},
        {"mom_1m": 0.05, "volume_trend": 1.2},
    )
    assert thesis.startswith("短期")
    assert risks[:2] == ["需給悪化", "規制"]


@patch("src.agents.perplexity_agent.requests.post")
def test_perplexity_payload_has_max_tokens_and_longer_instruction(mock_post, monkeypatch):
    monkeypatch.setenv("PPLX_API_KEY", "dummy")

    captured_payload = {}

    def _capture(*args, **kwargs):
        nonlocal captured_payload
        captured_payload = kwargs.get("json", {})
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "{\"thesis\":\"長めの出力\",\"risks\":[\"A\"]}"}}]}
        mock_resp.raise_for_status = lambda: None
        return mock_resp

    mock_post.side_effect = _capture

    generate_thesis_and_risks(
        "TEST", "Test Corp", "US",
        {"fundamental": 0.7, "growth": 0.6},
        {"mom_1m": 0.05, "volume_trend": 1.2},
    )

    # max_tokens が含まれる
    assert isinstance(captured_payload.get("max_tokens"), int)
    # systemに長めの指示（2-4文程度/過度に短すぎない）が含まれていることを緩く確認
    system_msg = captured_payload.get("messages", [{}])[0].get("content", "")
    assert "過度に短すぎない" in system_msg
