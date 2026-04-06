import pandas as pd
import pandas_ta as ta
from typing import Dict, Any, List
import logging

logger = logging.getLogger("TechnicalEngine")

class TechnicalEngine:
    """
    Motore tecnico puro (stateless) per il calcolo degli indicatori.
    V12: Aggiunto Multi-Timeframe Analysis per conferma segnali.
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
    def analyze_multi_timeframe(
        df_5m: pd.DataFrame,
        df_1h: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        V12: Analisi Multi-Timeframe.
        Combina segnali 5m con conferma dal timeframe 1h.
        
        Returns dict con:
          - analysis_5m: analisi standard 5m
          - htf_regime: regime trend su 1h (TREND_UP/DOWN/SIDEWAYS)
          - htf_rsi: RSI su 1h
          - htf_macd_bullish: se MACD 1h è bullish
          - htf_alignment: True se 5m e 1h concordano
          - confidence_penalty: riduzione % di confidence se non allineati
        """
        result = {
            "htf_regime": "UNKNOWN",
            "htf_rsi": 50.0,
            "htf_macd_bullish": False,
            "htf_alignment": False,
            "confidence_penalty": 0,
        }
        
        # Analisi 5m standard
        analysis_5m = TechnicalEngine.analyze_market(df_5m)
        result["analysis_5m"] = analysis_5m
        
        if not analysis_5m:
            return result
        
        # Analisi 1h
        try:
            if df_1h is None or len(df_1h) < 30:
                logger.warning("Dati 1h insufficienti per MTF analysis")
                return result
            
            df_1h = df_1h.copy()
            df_1h['rsi'] = ta.rsi(df_1h['close'], length=14)
            macd_1h = ta.macd(df_1h['close'])
            df_1h['macd'] = macd_1h['MACD_12_26_9']
            df_1h['macd_s'] = macd_1h['MACDs_12_26_9']
            df_1h['ema200'] = ta.ema(df_1h['close'], length=200)
            
            latest_1h = df_1h.iloc[-1]
            price_1h = float(latest_1h['close'])
            ema200_1h = float(latest_1h['ema200'])
            rsi_1h = float(latest_1h['rsi'])
            macd_1h_val = float(latest_1h['macd'])
            macd_s_1h = float(latest_1h['macd_s'])
            
            # Regime 1h
            if price_1h > ema200_1h * 1.005:
                htf_regime = "TREND_UP"
            elif price_1h < ema200_1h * 0.995:
                htf_regime = "TREND_DOWN"
            else:
                htf_regime = "SIDEWAYS"
            
            macd_bullish = macd_1h_val > macd_s_1h
            
            result["htf_regime"] = htf_regime
            result["htf_rsi"] = rsi_1h
            result["htf_macd_bullish"] = macd_bullish
            
            # Check allineamento
            regime_5m = analysis_5m.get("regime", "SIDEWAYS")
            signal_5m = analysis_5m.get("signal", "NEUTRAL")
            
            # Allineamento: entrambi bullish o entrambi bearish
            both_bullish = (
                regime_5m in ("TREND_UP",) and 
                htf_regime in ("TREND_UP",) and 
                macd_bullish
            )
            buy_with_htf_support = (
                signal_5m == "BUY_ZONE" and 
                htf_regime != "TREND_DOWN" and
                rsi_1h < 70
            )
            
            result["htf_alignment"] = both_bullish or buy_with_htf_support
            
            # Penalità se non allineati
            if not result["htf_alignment"]:
                if htf_regime == "TREND_DOWN" and signal_5m == "BUY_ZONE":
                    result["confidence_penalty"] = 20  # Forte penalità: compra contro trend 1h
                elif htf_regime == "SIDEWAYS":
                    result["confidence_penalty"] = 10  # Penalità media: nessuna conferma
                else:
                    result["confidence_penalty"] = 5   # Penalità lieve
                    
            logger.info(
                f"MTF: 5m={regime_5m}/{signal_5m} | 1h={htf_regime} RSI={rsi_1h:.0f} MACD={'bull' if macd_bullish else 'bear'} | "
                f"Aligned={result['htf_alignment']} Penalty={result['confidence_penalty']}%"
            )
            
        except Exception as e:
            logger.error(f"Errore Multi-Timeframe analysis: {e}")
        
        return result

    @staticmethod
    def get_stop_levels(price: float, atr: float, side: str = "long") -> Dict[str, float]:
        """
        Calcola livelli di uscita intelligenti basati sulla volatilità (ATR).
        V12: Dynamic multipliers basati sulla volatilità relativa.
        """
        # ATR% del prezzo per regolare aggressività
        atr_pct = (atr / price * 100) if price > 0 else 3.0
        
        # Volatilità alta → SL più largo, TP più ambizioso
        if atr_pct > 5.0:
            sl_mult = 2.0
            tp_mult = 3.5
            trail_mult = 1.5
        elif atr_pct > 2.5:
            sl_mult = 1.5
            tp_mult = 2.5
            trail_mult = 1.0
        else:
            sl_mult = 1.2
            tp_mult = 2.0
            trail_mult = 0.8

        if side == "long":
            return {
                "sl": price - (atr * sl_mult),
                "tp": price + (atr * tp_mult),
                "trailing_activation": price + (atr * trail_mult)
            }
        else:
            return {
                "sl": price + (atr * sl_mult),
                "tp": price - (atr * tp_mult),
                "trailing_activation": price - (atr * trail_mult)
            }

