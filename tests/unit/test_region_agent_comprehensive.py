import pytest
from datetime import date
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np

from src.agents.regions import RegionAgent
from src.tools.marketdata import MarketDataClient
from src.tools.fundamentals import FundamentalsClient
from src.tools.news import NewsClient


class TestRegionAgentComprehensive:
    """RegionAgent.runの包括的なテスト"""

    def setup_method(self):
        """テスト前のセットアップ"""
        self.agent = RegionAgent(name="JP", universe="REAL", tools={})
        self.as_of = date(2025, 8, 15)
        self.top_n = 10

    def test_region_agent_with_real_data_success(self):
        """実データ経路の成功ケース"""
        # モックデータの準備
        mock_prices = pd.DataFrame({
            '7203.T': [100, 101, 102],
            '6758.T': [200, 201, 202]
        }, index=pd.date_range('2025-01-01', periods=3))
        
        mock_volumes = pd.DataFrame({
            '7203.T': [1000, 1100, 1200],
            '6758.T': [2000, 2100, 2200]
        }, index=pd.date_range('2025-01-01', periods=3))
        
        mock_fundamentals = pd.DataFrame({
            'ticker': ['7203.T', '6758.T'],
            'roic': [0.15, 0.20],
            'fcf_margin': [0.10, 0.12],
            'revenue_cagr': [0.05, 0.08],
            'eps_growth': [0.03, 0.06]
        })
        
        mock_news = [
            {'ticker': '7203.T', 'title': 'Toyota beats estimates', 'url': 'http://example.com', 'date': '2025-08-15'},
            {'ticker': '6758.T', 'title': 'Sony reports strong growth', 'url': 'http://example.com', 'date': '2025-08-15'}
        ]

        with patch('src.agents.regions.load_universe') as mock_load_universe, \
             patch('src.agents.regions.build_features_from_prices') as mock_build_features, \
             patch('src.agents.regions.merge_fundamentals') as mock_merge_fundamentals, \
             patch('src.agents.regions.merge_news_signal') as mock_merge_news, \
             patch('src.agents.regions.normalize_features') as mock_normalize, \
             patch('src.agents.regions.score_candidates') as mock_score, \
             patch('src.agents.regions.is_openai_configured', return_value=False):
            
            # モックの設定
            mock_load_universe.return_value = pd.DataFrame({
                'ticker': ['7203.T', '6758.T'],
                'name': ['Toyota Motor', 'Sony Group']
            })
            
            mock_build_features.return_value = pd.DataFrame({
                'ticker': ['7203.T', '6758.T'],
                'name': ['Toyota Motor', 'Sony Group'],
                'fundamental_roic': [0.5, 0.6],
                'fundamental_fcf_margin': [0.4, 0.5],
                'technical_mom_12m': [0.1, 0.2],
                'technical_volume_trend': [0.3, 0.4],
                'quality_dilution': [0.7, 0.8],
                'news_signal': [0.5, 0.6]
            })
            
            mock_merge_fundamentals.return_value = mock_build_features.return_value
            mock_merge_news.return_value = mock_build_features.return_value
            mock_normalize.return_value = mock_build_features.return_value
            
            mock_score.return_value = pd.DataFrame({
                'ticker': ['7203.T', '6758.T'],
                'name': ['Toyota Motor', 'Sony Group'],
                'score_overall': [0.8, 0.9],
                'score_fundamental': [0.7, 0.8],
                'score_technical': [0.6, 0.7],
                'score_quality': [0.5, 0.6],
                'score_news': [0.4, 0.5],
                'score_growth': [0.3, 0.4]
            })

            # ツールのモック
            mock_marketdata = Mock(spec=MarketDataClient)
            mock_marketdata.get_prices.return_value = (mock_prices, mock_volumes)
            
            mock_fundamentals = Mock(spec=FundamentalsClient)
            mock_fundamentals.get_fundamentals.return_value = mock_fundamentals
            
            mock_news = Mock(spec=NewsClient)
            mock_news.get_news.return_value = mock_news
            
            self.agent.tools = {
                'marketdata': mock_marketdata,
                'fundamentals': mock_fundamentals,
                'news': mock_news
            }

            # 実行
            result = self.agent.run(as_of=self.as_of, top_n=self.top_n)

            # 検証
            assert result['region'] == 'JP'
            assert result['as_of'] == '2025-08-15'
            assert result['universe'] == 'REAL'
            assert len(result['candidates']) == 2
            assert len(result['growth_candidates']) == 2
            
            # 各ステップが呼ばれたことを確認
            mock_load_universe.assert_called_once_with('JP')
            mock_marketdata.get_prices.assert_called_once()
            mock_build_features.assert_called_once()
            mock_merge_fundamentals.assert_called_once()
            mock_merge_news.assert_called_once()
            mock_normalize.assert_called_once()
            mock_score.assert_called_once()

    def test_region_agent_fallback_to_dummy_data(self):
        """フォールバック: ダミーデータ生成"""
        with patch('src.agents.regions.load_universe', side_effect=Exception("Data not available")), \
             patch('src.agents.regions.build_features_from_dummy') as mock_build_dummy, \
             patch('src.agents.regions.normalize_features') as mock_normalize, \
             patch('src.agents.regions.score_candidates') as mock_score, \
             patch('src.agents.regions.is_openai_configured', return_value=False):
            
            # モックの設定
            mock_build_dummy.return_value = pd.DataFrame({
                'ticker': ['JP001', 'JP002'],
                'name': ['JP-Company-001', 'JP-Company-002'],
                'fundamental_roic': [0.5, 0.6],
                'fundamental_fcf_margin': [0.4, 0.5],
                'technical_mom_12m': [0.1, 0.2],
                'technical_volume_trend': [0.3, 0.4],
                'quality_dilution': [0.7, 0.8],
                'news_signal': [0.5, 0.6]
            })
            
            mock_normalize.return_value = mock_build_dummy.return_value
            mock_score.return_value = pd.DataFrame({
                'ticker': ['JP001', 'JP002'],
                'name': ['JP-Company-001', 'JP-Company-002'],
                'score_overall': [0.8, 0.9],
                'score_fundamental': [0.7, 0.8],
                'score_technical': [0.6, 0.7],
                'score_quality': [0.5, 0.6],
                'score_news': [0.4, 0.5],
                'score_growth': [0.3, 0.4]
            })

            # 実行
            result = self.agent.run(as_of=self.as_of, top_n=self.top_n)

            # 検証
            assert result['region'] == 'JP'
            assert result['universe'] == 'REAL'
            assert len(result['candidates']) == 2
            assert len(result['growth_candidates']) == 2
            
            # ダミーデータ生成が呼ばれたことを確認
            mock_build_dummy.assert_called_once_with(region='JP', as_of=self.as_of)

    def test_region_agent_openai_not_configured(self):
        """OpenAI未設定時の安定性"""
        with patch('src.agents.regions.load_universe') as mock_load_universe, \
             patch('src.agents.regions.build_features_from_dummy') as mock_build_dummy, \
             patch('src.agents.regions.normalize_features') as mock_normalize, \
             patch('src.agents.regions.score_candidates') as mock_score, \
             patch('src.agents.regions.is_openai_configured', return_value=False):
            
            # モックの設定
            mock_load_universe.side_effect = Exception("Data not available")
            
            mock_build_dummy.return_value = pd.DataFrame({
                'ticker': ['JP001'],
                'name': ['JP-Company-001'],
                'fundamental_roic': [0.5],
                'fundamental_fcf_margin': [0.4],
                'technical_mom_12m': [0.1],
                'technical_volume_trend': [0.3],
                'quality_dilution': [0.7],
                'news_signal': [0.5]
            })
            
            mock_normalize.return_value = mock_build_dummy.return_value
            mock_score.return_value = pd.DataFrame({
                'ticker': ['JP001'],
                'name': ['JP-Company-001'],
                'score_overall': [0.8],
                'score_fundamental': [0.7],
                'score_technical': [0.6],
                'score_quality': [0.5],
                'score_news': [0.4],
                'score_growth': [0.3]
            })

            # 実行
            result = self.agent.run(as_of=self.as_of, top_n=self.top_n)

            # 検証
            assert result['region'] == 'JP'
            assert len(result['candidates']) == 1
            assert len(result['growth_candidates']) == 1
            
            # デフォルトのthesisとrisksが設定されていることを確認
            candidate = result['candidates'][0]
            assert 'thesis' in candidate
            assert 'risks' in candidate
            assert isinstance(candidate['thesis'], str)
            assert isinstance(candidate['risks'], list)

    def test_region_agent_empty_data_handling(self):
        """空データの処理"""
        with patch('src.agents.regions.load_universe') as mock_load_universe, \
             patch('src.agents.regions.build_features_from_prices') as mock_build_features, \
             patch('src.agents.regions.build_features_from_dummy') as mock_build_dummy, \
             patch('src.agents.regions.normalize_features') as mock_normalize, \
             patch('src.agents.regions.score_candidates') as mock_score, \
             patch('src.agents.regions.is_openai_configured', return_value=False):
            
            # 空のデータを返すように設定
            mock_load_universe.return_value = pd.DataFrame({
                'ticker': ['7203.T'],
                'name': ['Toyota Motor']
            })
            
            mock_build_features.return_value = pd.DataFrame()  # 空のDataFrame
            
            mock_build_dummy.return_value = pd.DataFrame({
                'ticker': ['JP001'],
                'name': ['JP-Company-001'],
                'fundamental_roic': [0.5],
                'fundamental_fcf_margin': [0.4],
                'technical_mom_12m': [0.1],
                'technical_volume_trend': [0.3],
                'quality_dilution': [0.7],
                'news_signal': [0.5]
            })
            
            mock_normalize.return_value = mock_build_dummy.return_value
            mock_score.return_value = pd.DataFrame({
                'ticker': ['JP001'],
                'name': ['JP-Company-001'],
                'score_overall': [0.8],
                'score_fundamental': [0.7],
                'score_technical': [0.6],
                'score_quality': [0.5],
                'score_news': [0.4],
                'score_growth': [0.3]
            })

            # ツールのモック
            mock_marketdata = Mock(spec=MarketDataClient)
            mock_marketdata.get_prices.return_value = (pd.DataFrame(), pd.DataFrame())
            
            self.agent.tools = {'marketdata': mock_marketdata}

            # 実行
            result = self.agent.run(as_of=self.as_of, top_n=self.top_n)

            # 検証
            assert result['region'] == 'JP'
            assert len(result['candidates']) == 1
            assert len(result['growth_candidates']) == 1
            
            # フォールバックが呼ばれたことを確認
            mock_build_dummy.assert_called_once()

    def test_region_agent_top_n_limitation(self):
        """top_n制限の動作確認"""
        with patch('src.agents.regions.load_universe') as mock_load_universe, \
             patch('src.agents.regions.build_features_from_dummy') as mock_build_dummy, \
             patch('src.agents.regions.normalize_features') as mock_normalize, \
             patch('src.agents.regions.score_candidates') as mock_score, \
             patch('src.agents.regions.is_openai_configured', return_value=False):
            
            # 10個の候補を生成
            mock_build_dummy.return_value = pd.DataFrame({
                'ticker': [f'JP{i:03d}' for i in range(10)],
                'name': [f'JP-Company-{i:03d}' for i in range(10)],
                'fundamental_roic': [0.5] * 10,
                'fundamental_fcf_margin': [0.4] * 10,
                'technical_mom_12m': [0.1] * 10,
                'technical_volume_trend': [0.3] * 10,
                'quality_dilution': [0.7] * 10,
                'news_signal': [0.5] * 10
            })
            
            mock_normalize.return_value = mock_build_dummy.return_value
            mock_score.return_value = pd.DataFrame({
                'ticker': [f'JP{i:03d}' for i in range(10)],
                'name': [f'JP-Company-{i:03d}' for i in range(10)],
                'score_overall': [0.9 - i * 0.1 for i in range(10)],  # 降順
                'score_fundamental': [0.7] * 10,
                'score_technical': [0.6] * 10,
                'score_quality': [0.5] * 10,
                'score_news': [0.4] * 10,
                'score_growth': [0.3] * 10
            })

            # top_n=3で実行
            result = self.agent.run(as_of=self.as_of, top_n=3)

            # 検証
            assert len(result['candidates']) == 3
            assert len(result['growth_candidates']) == 3
            
            # スコア順になっていることを確認
            scores = [c['score_overall'] for c in result['candidates']]
            assert scores == sorted(scores, reverse=True)
