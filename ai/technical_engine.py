import pandas as pd
import pandas_ta as ta
from typing import Dict, Any, List
import logging

logger = logging.getLogger("TechnicalEngine")

class TechnicalEngine:
    """
    Motore tecnico puro (stateless) per il calcolo degli indicatori.
    Ottimizzato per velocità e precisione (Pattern: src/utils/ in Claude Code).
    """
    
    @staticmethod
    def analyze_market(df: pd.DataFrame) -> Dict[str, Any]:
        """Esegue l'analisi tecnica completa su un DataFrame di candele."""
        if df is None or len(df) < 30:
            return {}

        try:
            # Indicatori Trend
            df['rsi'] = ta.rsi(df['close'], length=14)
            macd = ta.macd(df['close'])
            df['macd'] = macd['MACD_12_26_9']
            df['macd_s'] = macd['MACDs_12_26_9']
            
            # Indicatori Volatilità (fondamentali per SL/TP)
            df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
            
            # Media Mobile per il Regime
            df['ema200'] = ta.ema(df['close'], length=200)
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            # Calcolo Regime
            price = latest['close']
            ema200 = latest['ema200']
            
            regime = "SIDEWAYS"
            if price > ema200 * 1.002: # 0.2% buffer
                regime = "TREND_UP"
            elif price < ema200 * 0.998:
                regime = "TREND_DOWN"
            
            # Calcolo segnali basici
            signal = "NEUTRAL"
            if latest['rsi'] < 30 and latest['macd'] > latest['macd_s']:
                signal = "BUY_ZONE"
            elif latest['rsi'] > 70 and latest['macd'] < latest['macd_s']:
                signal = "SELL_ZONE"
                
            return {
                "price": float(price),
                "rsi": float(latest['rsi']),
                "macd": float(latest['macd']),
                "atr": float(latest['atr']),
                "ema200": float(ema200),
                "regime": regime,
                "signal": signal,
                "volatility_ratio": float(latest['atr'] / price * 100),
                "trend_strength": float((price - ema200) / ema200 * 100)
            }
        except Exception as e:
            logger.error(f"Errore calcolo tecnico: {e}")
            return {}

    @staticmethod
    def get_stop_levels(price: float, atr: float, side: str = "long") -> Dict[str, float]:
        """Calcola livelli di uscita intelligenti basati sulla volatilità (ATR)."""
        if side == "long":
            return {
                "sl": price - (atr * 1.5),
                "tp": price + (atr * 2.5),
                "trailing_activation": price + (atr * 1.0)
            }
        else:
            return {
                "sl": price + (atr * 1.5),
                "tp": price - (atr * 2.5),
                "trailing_activation": price - (atr * 1.0)
            }
