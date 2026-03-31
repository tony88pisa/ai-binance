"""
VERIFY MODULE 11 — PHASE 1
Tests Regime Detection Engine with real-time data.
"""
import sys
from pathlib import Path
import logging

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Mocking a dataframe for technical indicators
import pandas as pd
import numpy as np

def create_mock_df(regime='bull'):
    data = {
        'high': np.linspace(100, 110, 30) if regime == 'bull' else np.linspace(110, 100, 30),
        'low': np.linspace(98, 108, 30) if regime == 'bull' else np.linspace(108, 98, 30),
        'close': np.linspace(99, 109, 30) if regime == 'bull' else np.linspace(109, 99, 30),
    }
    return pd.DataFrame(data)

from ai.regime_detector import RegimeDetector, MarketRegime
from ai.external_data import ExternalDataProvider

def test_phase1_logic():
    print("--- VERIFICA MODULO 11: REGIME DETECTION ---")
    
    # 1. External Data Test
    print("[1/3] Testing ExternalDataProvider...")
    ext = ExternalDataProvider.get_global_context()
    print(f"Fear & Greed: {ext['fear_greed']}")
    print(f"Funding Rate: {ext['avg_funding']}")
    
    # 2. Regime Detection Test (Technical)
    print("\n[2/3] Testing RegimeDetector (New Labels)...")
    detector = RegimeDetector()
    df_bull = create_mock_df('bull')
    sig = detector.detect_asset_regime(df_bull, "BTC/USDT")
    print(f"Asset Regime (Bull Data): {sig.regime} (Conf: {sig.confidence}%)")
    
    # 3. Global Regime Fusion Test
    print("\n[3/3] Testing Global Regime Fusion (Logic Module 11)...")
    
    # Case A: High Fear + Bullish Momentum = RECOVERY?
    ext_recovery = {"fear_greed": 15, "avg_funding": 0.005}
    gr_a = detector.detect_global_regime([sig], ext_recovery)
    print(f"Scenario RECOVERY (Fear 15): {gr_a.regime} (Rec: {gr_a.strategy_recommendation})")
    
    # Case B: High Greed + High Funding = CRASH Warning?
    ext_crash = {"fear_greed": 85, "avg_funding": 0.04}
    gr_b = detector.detect_global_regime([sig], ext_crash)
    print(f"Scenario CRASH (Greed 85): {gr_b.regime} (Rec: {gr_b.strategy_recommendation})")
    
    print("\n--- TEST PHASE 1 COMPLETATO ---")

if __name__ == "__main__":
    test_phase1_logic()
