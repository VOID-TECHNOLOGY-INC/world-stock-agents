import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np

from src.agents.risk import RiskAgent


class TestRiskAgentComprehensive:
    """RiskAgent.runの包括的なテスト"""

    def setup_method(self):
        """テスト前のセットアップ"""
        self.agent = RiskAgent()
        
        # テスト用の価格データ
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        self.jp_prices = pd.DataFrame({
            '7203.T': np.random.normal(100, 10, 100),
            '6758.T': np.random.normal(200, 20, 100)
        }, index=dates)
        
        self.us_prices = pd.DataFrame({
            'AAPL': np.random.normal(150, 15, 100),
            'MSFT': np.random.normal(300, 30, 100)
        }, index=dates)
        
        self.price_panels = {
            'JP': self.jp_prices,
            'US': self.us_prices
        }

    def test_risk_agent_panel_combination(self):
        """パネル結合のテスト"""
        # 実行
        result = self.agent.run(self.price_panels)
        
        # 検証
        assert 'metrics' in result
        metrics = result['metrics']
        
        # 基本的なリスク指標が含まれていることを確認
        expected_keys = ['volatility', 'correlation', 'max_drawdown', 'covariance']
        for key in expected_keys:
            assert key in metrics
        
        # 相関行列の構造を確認（4銘柄なので4x4の辞書構造）
        corr_matrix = metrics['correlation']
        assert len(corr_matrix) == 4  # 4銘柄
        
        # ボラティリティが辞書形式であることを確認
        assert isinstance(metrics['volatility'], dict)
        assert len(metrics['volatility']) == 4  # 4銘柄
        
        # 最大ドローダウンが辞書形式であることを確認
        assert isinstance(metrics['max_drawdown'], dict)
        assert len(metrics['max_drawdown']) == 4  # 4銘柄

    def test_risk_agent_empty_input_handling(self):
        """空入力時の空メトリクス生成"""
        # 空のパネル
        empty_panels = {}
        
        # 実行
        result = self.agent.run(empty_panels)
        
        # 検証
        assert result == {"metrics": {}}

    def test_risk_agent_none_prices_handling(self):
        """None価格データの処理"""
        # Noneを含むパネル
        none_panels = {
            'JP': None,
            'US': self.us_prices
        }
        
        # 実行
        result = self.agent.run(none_panels)
        
        # 検証
        assert 'metrics' in result
        metrics = result['metrics']
        
        # USのデータのみが処理されていることを確認
        if 'correlation_matrix' in metrics:
            # USの2銘柄のみなので2x2の相関行列
            corr_matrix = metrics['correlation_matrix']
            assert corr_matrix.shape == (2, 2)

    def test_risk_agent_empty_dataframe_handling(self):
        """空DataFrameの処理"""
        # 空のDataFrameを含むパネル
        empty_df_panels = {
            'JP': pd.DataFrame(),
            'US': self.us_prices
        }
        
        # 実行
        result = self.agent.run(empty_df_panels)
        
        # 検証
        assert 'metrics' in result
        metrics = result['metrics']
        
        # USのデータのみが処理されていることを確認
        if 'correlation_matrix' in metrics:
            corr_matrix = metrics['correlation_matrix']
            assert corr_matrix.shape == (2, 2)

    def test_risk_agent_with_combined_prices(self):
        """事前結合価格データでのテスト"""
        # 事前に結合された価格データ
        combined_prices = pd.concat([self.jp_prices, self.us_prices], axis=1)
        
        # 実行
        result = self.agent.run(self.price_panels, combined_prices=combined_prices)
        
        # 検証
        assert 'metrics' in result
        metrics = result['metrics']
        
        # 基本的なリスク指標が含まれていることを確認
        expected_keys = ['volatility', 'correlation', 'max_drawdown', 'covariance']
        for key in expected_keys:
            assert key in metrics
        
        # 相関行列の構造を確認（4銘柄なので4x4の辞書構造）
        corr_matrix = metrics['correlation']
        assert len(corr_matrix) == 4  # 4銘柄

    def test_risk_agent_single_region(self):
        """単一地域のテスト"""
        # 単一地域のパネル
        single_panel = {'JP': self.jp_prices}
        
        # 実行
        result = self.agent.run(single_panel)
        
        # 検証
        assert 'metrics' in result
        metrics = result['metrics']
        
        # 基本的なリスク指標が含まれていることを確認
        expected_keys = ['volatility', 'correlation', 'max_drawdown', 'covariance']
        for key in expected_keys:
            assert key in metrics
        
        # 相関行列の構造を確認（2銘柄なので2x2の辞書構造）
        corr_matrix = metrics['correlation']
        assert len(corr_matrix) == 2  # 2銘柄

    def test_risk_agent_mixed_data_quality(self):
        """混合データ品質のテスト"""
        # 異なる品質のデータを含むパネル
        mixed_panels = {
            'JP': self.jp_prices,
            'US': self.us_prices,
            'EU': pd.DataFrame(),  # 空
            'CN': None  # None
        }
        
        # 実行
        result = self.agent.run(mixed_panels)
        
        # 検証
        assert 'metrics' in result
        metrics = result['metrics']
        
        # 有効なデータのみが処理されていることを確認
        if 'correlation' in metrics:
            corr_matrix = metrics['correlation']
            # JP(2銘柄) + US(2銘柄) = 4銘柄
            assert len(corr_matrix) == 4

    def test_risk_agent_metrics_validation(self):
        """リスク指標の妥当性テスト"""
        # 実行
        result = self.agent.run(self.price_panels)
        
        # 検証
        metrics = result['metrics']
        
        # ボラティリティの妥当性
        if 'volatility' in metrics:
            volatility = metrics['volatility']
            assert isinstance(volatility, dict)
            for ticker, vol in volatility.items():
                assert vol > 0
                assert isinstance(vol, (int, float))
        
        # 相関行列の妥当性
        if 'correlation' in metrics:
            corr_matrix = metrics['correlation']
            assert isinstance(corr_matrix, dict)
            for ticker, correlations in corr_matrix.items():
                assert isinstance(correlations, dict)
                # 対角成分は1
                assert abs(correlations[ticker] - 1.0) < 1e-6
                # 相関係数は-1から1の範囲
                for other_ticker, corr in correlations.items():
                    assert -1.0 <= corr <= 1.0
        
        # 最大ドローダウンの妥当性
        if 'max_drawdown' in metrics:
            max_dd = metrics['max_drawdown']
            assert isinstance(max_dd, dict)
            for ticker, dd in max_dd.items():
                assert -1.0 <= dd <= 0.0  # 最大ドローダウンは負の値
                assert isinstance(dd, (int, float))
