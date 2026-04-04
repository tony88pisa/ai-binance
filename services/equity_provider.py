import yfinance as yf
import pandas as pd
from datetime import datetime

class EquityProvider:
    """
    Fetches Traditional Markets (Equities, Indices) from Yahoo Finance.
    Provides OHLCV similar to ccxt for AI agents to easily plug in.
    """
    
    def __init__(self):
        # Tracking tickers for different markets
        self.markets = {
            "USA": ["AAPL", "NVDA", "TSLA", "SPY", "MSFT", "AMZN", "META", "GOOGL"],
            "EUROPE": ["BMW.DE", "STM.MI", "LVMUY", "ENI.MI", "ENEL.MI", "SAP.DE"],
            "CHINA": ["0700.HK", "BABA", "NIO", "9988.HK"],
            "COMMODITIES": ["GC=F", "SI=F", "CL=F"]  # Gold, Silver, Oil futures via Yahoo
        }
        
    def get_market_list(self, region: str = "ALL"):
        if region == "ALL":
            all_assets = []
            for r in self.markets.values():
                all_assets.extend(r)
            return all_assets
        return self.markets.get(region, [])

    def get_ohlcv(self, ticker: str, timeframe: str = "5m", limit: int = 100) -> pd.DataFrame:
        """
        Fetch OHLCV data using yfinance.
        yfinance interval formats: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
        """
        try:
            stock = yf.Ticker(ticker)
            
            # For 5m we can only get max 60 days via YFinance free tier
            period = "1mo" 
            if timeframe in ["1d", "1wk", "1mo"]:
                period = "1y"
                
            df = stock.history(period=period, interval=timeframe)
            if df.empty:
                return pd.DataFrame()
            
            df = df.reset_index()
            col_date = 'Datetime' if 'Datetime' in df.columns else 'Date'
            
            df = df.rename(columns={
                col_date: 'timestamp',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            df['timestamp'] = pd.to_datetime(df['timestamp']).values.astype('int64') // 10**6 # to ms
            
            cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            df = df[cols].tail(limit)
            return df
        except Exception as e:
            print(f"[EquityProvider] Error fetching {ticker}: {e}")
            return pd.DataFrame()
            
    def get_current_price(self, ticker: str) -> float:
        """Get the latest price for a stock."""
        try:
            stock = yf.Ticker(ticker)
            info = stock.fast_info
            if 'last_price' in info:
                return float(info['last_price'])
            
            df = self.get_ohlcv(ticker, "1m", limit=1)
            if not df.empty:
                return float(df.iloc[-1]['close'])
        except Exception:
            pass
        return 0.0

    def is_market_open(self, region: str) -> bool:
        """
        Rough heuristic for market hours.
        In a real scenario, use pandas_market_calendars, but we simulate it closely.
        USA: 09:30 - 16:00 EST
        EUR: 09:00 - 17:30 CET
        CHINA (HK): 09:30 - 16:00 HKT
        Instead of strict timezones, let's just return True for demo so agents can always research.
        """
        return True
