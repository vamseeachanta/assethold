"""Tests for portfolio beta vs energy benchmarks."""
import pytest
import numpy as np


class TestPortfolioBeta:
    def test_beta_perfect_correlation(self):
        """Beta of asset identical to benchmark = 1.0"""
        from assethold.risk_metrics import calculate_beta
        returns = np.array([0.01, -0.02, 0.03, -0.01, 0.02])
        benchmark = np.array([0.01, -0.02, 0.03, -0.01, 0.02])
        result = calculate_beta(returns, benchmark)
        assert abs(result.beta - 1.0) < 1e-10

    def test_beta_double_leverage(self):
        """Asset with 2x benchmark returns has beta ~ 2.0"""
        from assethold.risk_metrics import calculate_beta
        benchmark = np.array([0.01, -0.02, 0.03, -0.01, 0.02])
        returns = benchmark * 2
        result = calculate_beta(returns, benchmark)
        assert abs(result.beta - 2.0) < 1e-6

    def test_beta_zero_correlation(self):
        """Uncorrelated asset has beta ~ 0"""
        from assethold.risk_metrics import calculate_beta
        np.random.seed(42)
        returns = np.random.normal(0, 0.01, 100)
        benchmark = np.random.normal(0, 0.01, 100)
        result = calculate_beta(returns, benchmark)
        assert abs(result.beta) < 0.5  # roughly zero

    def test_beta_result_has_r_squared(self):
        from assethold.risk_metrics import calculate_beta
        returns = np.array([0.01, -0.02, 0.03, -0.01, 0.02])
        benchmark = np.array([0.01, -0.02, 0.03, -0.01, 0.02])
        result = calculate_beta(returns, benchmark)
        assert hasattr(result, 'r_squared')
        assert 0 <= result.r_squared <= 1.0

    def test_beta_mismatched_lengths_raises(self):
        from assethold.risk_metrics import calculate_beta
        with pytest.raises(ValueError):
            calculate_beta(np.array([0.01, 0.02]), np.array([0.01]))

    def test_beta_insufficient_data_raises(self):
        from assethold.risk_metrics import calculate_beta
        with pytest.raises(ValueError):
            calculate_beta(np.array([0.01]), np.array([0.01]))
