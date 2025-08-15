"""テクニカル指標をLLMに渡す機能のテスト"""

import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from src.agents.openai_agent import generate_thesis_and_risks
from src.scoring.features import build_features_from_dummy
from src.agents.regions import RegionAgent
from datetime import date


class TestTechnicalLLMAnalysis:
    """テクニカル指標をLLMに渡す機能のテスト"""

    def test_generate_thesis_and_risks_with_technical_indicators(self):
        """テクニカル指標を含む分析の生成をテスト"""
        features = {
            "fundamental": 0.7,
            "technical": 0.8,
            "quality": 0.6,
            "news": 0.5,
            "growth": 0.4,
        }
        
        technical_indicators = {
            "mom_12m": 0.15,  # 15%
            "mom_6m": 0.08,   # 8%
            "mom_3m": 0.03,   # 3%
            "mom_1m": 0.01,   # 1%
            "volume_trend": 1.25,  # 25%増加
        }
        
        with patch("src.agents.openai_agent.is_openai_configured", return_value=False):
            thesis, risks = generate_thesis_and_risks(
                "TEST", "Test Company", "US", features, technical_indicators
            )
        
        # フォールバック動作を確認
        assert "Test Company" in thesis
        assert isinstance(risks, list)
        assert len(risks) == 3

    def test_dummy_features_include_raw_technical(self):
        """ダミーデータに生のテクニカル指標が含まれることをテスト"""
        df = build_features_from_dummy("TEST", date(2025, 8, 15), size=5)
        
        # 基本構造の確認
        assert len(df) == 5
        assert "_raw_technical" in df.columns
        
        # 生のテクニカル指標の確認
        for _, row in df.iterrows():
            raw_tech = row["_raw_technical"]
            assert isinstance(raw_tech, dict)
            assert "mom_12m" in raw_tech
            assert "mom_6m" in raw_tech
            assert "mom_3m" in raw_tech
            assert "mom_1m" in raw_tech
            assert "volume_trend" in raw_tech

    @patch("src.agents.regions.is_openai_configured")
    @patch("src.agents.regions.generate_thesis_and_risks")
    def test_region_agent_passes_technical_indicators(self, mock_generate, mock_configured):
        """RegionAgentがテクニカル指標をLLMに渡すことをテスト"""
        mock_configured.return_value = True
        mock_generate.return_value = ("Test thesis", ["Risk 1", "Risk 2"])
        
        agent = RegionAgent("TEST", "dummy", {})
        
        with patch("src.agents.regions.load_universe") as mock_load:
            mock_load.side_effect = Exception("Force fallback to dummy")
            
            result = agent.run(date(2025, 8, 15), top_n=3)
        
        # generate_thesis_and_risksが呼ばれたことを確認
        assert mock_generate.called
        
        # 呼び出し引数を確認
        call_args = mock_generate.call_args
        assert len(call_args[0]) == 5  # ticker, name, region, features, technical_indicators
        
        # technical_indicatorsが渡されていることを確認
        technical_indicators = call_args[0][4]
        assert isinstance(technical_indicators, dict)
        
        # 出力にtechnical_indicatorsが含まれていることを確認
        candidates = result["candidates"]
        assert len(candidates) > 0
        assert "technical_indicators" in candidates[0]

    def test_technical_indicators_in_output_format(self):
        """出力フォーマットにテクニカル指標が含まれることをテスト"""
        agent = RegionAgent("TEST", "dummy", {})
        
        with patch("src.agents.regions.load_universe") as mock_load:
            mock_load.side_effect = Exception("Force fallback to dummy")
            
            result = agent.run(date(2025, 8, 15), top_n=2)
        
        # 基本構造の確認
        assert "candidates" in result
        candidates = result["candidates"]
        assert len(candidates) > 0
        
        # 各候補のテクニカル指標を確認
        for candidate in candidates:
            assert "technical_indicators" in candidate
            tech_indicators = candidate["technical_indicators"]
            assert isinstance(tech_indicators, dict)
            
            # 期待される指標の確認
            expected_keys = ["mom_12m", "mom_6m", "mom_3m", "mom_1m", "volume_trend"]
            for key in expected_keys:
                assert key in tech_indicators

    def test_technical_indicators_formatting(self):
        """テクニカル指標の値の形式をテスト"""
        # 実際のテクニカル指標データをシミュレート
        mock_row = pd.Series({
            "_raw_technical": {
                "mom_12m": 0.15,
                "mom_6m": 0.08,
                "mom_3m": None,  # 欠損値
                "mom_1m": float("nan"),  # NaN
                "volume_trend": 1.25,
            }
        })
        
        # RegionAgentの処理をシミュレート
        raw_technical = mock_row.get("_raw_technical", {})
        technical_indicators = {}
        if raw_technical:
            for k, v in raw_technical.items():
                if v is not None and not pd.isna(v):
                    technical_indicators[k] = float(v)
                else:
                    technical_indicators[k] = None
        
        # 正しい変換を確認
        assert technical_indicators["mom_12m"] == 0.15
        assert technical_indicators["mom_6m"] == 0.08
        assert technical_indicators["mom_3m"] is None
        assert technical_indicators["mom_1m"] is None
        assert technical_indicators["volume_trend"] == 1.25
