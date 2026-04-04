"""
Centralized settings model.

Single source of truth for all configuration.
Loads from .env (secrets) and provides typed access.
Freqtrade's config.json remains its own config; this module
manages everything outside of Freqtrade's scope.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Load .env file into os.environ (no external dependency)."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        logger.warning(f".env not found at {env_path}")
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


# Load on import
_load_dotenv()


@dataclass(frozen=True)
class ExchangeSettings:
    name: str = "binance"
    mode: str = "simulation"  # simulation | testnet | live
    key: str = ""
    secret: str = ""
    password: str = ""
    testnet_key: str = ""
    testnet_secret: str = ""


@dataclass(frozen=True)
class TelegramSettings:
    enabled: bool = True
    token: str = ""
    chat_id: str = ""


@dataclass(frozen=True)
class DashboardSettings:
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8087
    username: str = ""
    password: str = ""
    jwt_secret: str = ""


@dataclass(frozen=True)
class ModelSettings:
    provider: str = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    model_name: str = "qwen3:8b"
    timeout_seconds: int = 90
    max_retries: int = 2
    temperature: float = 0.1
    max_tokens: int = 150
    validation_mode: str = "real"  # mock | cached | real


@dataclass(frozen=True)
class RiskSettings:
    max_open_trades: int = 3
    max_stake_pct: float = 0.33        # Max % of wallet per trade
    max_stake_abs: float = 20.0        # Hard cap in fiat per trade
    stoploss: float = -0.05
    max_consecutive_losses: int = 3     # Circuit breaker trigger
    max_daily_loss_pct: float = -0.10   # Max daily drawdown (not yet enforced)
    min_confidence_buy: int = 60        # Minimum AI confidence to buy
    min_confidence_high: int = 85       # High confidence threshold


@dataclass(frozen=True)
class TradingSettings:
    dry_run: bool = True
    wallet_size: float = 10000.0
    stake_currency: str = "USDT"
    timeframe: str = "5m"
    informative_timeframe: str = "1h"
    pairs: list[str] = field(default_factory=lambda: ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"])


@dataclass(frozen=True)
class NewsSettings:
    feeds: dict[str, str] = field(default_factory=lambda: {
        "cointelegraph": "https://cointelegraph.com/rss",
        "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "decrypt": "https://decrypt.co/feed"
    })
    feed_timeout: int = 10
    fng_timeout: int = 8
    fng_url: str = "https://api.alternative.me/fng/?limit=1&format=json"


@dataclass(frozen=True)
class PathSettings:
    project_root: Path = PROJECT_ROOT
    config_file: Path = field(default_factory=lambda: PROJECT_ROOT / "config.json")
    env_file: Path = field(default_factory=lambda: PROJECT_ROOT / ".env")
    memory_file: Path = field(default_factory=lambda: PROJECT_ROOT / "user_data" / "ai_agents" / "memory.json")
    inference_cache_file: Path = field(default_factory=lambda: PROJECT_ROOT / "user_data" / "inference_cache.json")
    log_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "user_data" / "logs")
    strategy_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "user_data" / "strategies")


@dataclass(frozen=True)
class Settings:
    """Master settings — single source of truth."""
    exchange: ExchangeSettings = field(default_factory=ExchangeSettings)
    telegram: TelegramSettings = field(default_factory=TelegramSettings)
    dashboard: DashboardSettings = field(default_factory=DashboardSettings)
    model: ModelSettings = field(default_factory=ModelSettings)
    risk: RiskSettings = field(default_factory=RiskSettings)
    trading: TradingSettings = field(default_factory=TradingSettings)
    news: NewsSettings = field(default_factory=NewsSettings)
    paths: PathSettings = field(default_factory=PathSettings)


def load_settings() -> Settings:
    """Build settings from environment variables and defaults."""
    return Settings(
        exchange=ExchangeSettings(
            name=os.getenv("EXCHANGE_NAME", "binance"),
            mode=os.getenv("EXCHANGE_MODE", "simulation").lower(),
            key=os.getenv("EXCHANGE_KEY", ""),
            secret=os.getenv("EXCHANGE_SECRET", ""),
            password=os.getenv("EXCHANGE_PASSWORD", ""),
            testnet_key=os.getenv("BINANCE_TESTNET_API_KEY", ""),
            testnet_secret=os.getenv("BINANCE_TESTNET_SECRET", ""),
        ),
        telegram=TelegramSettings(
            token=os.getenv("TELEGRAM_TOKEN", ""),
            chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        ),
        dashboard=DashboardSettings(
            host=os.getenv("DASHBOARD_HOST", "127.0.0.1"),
            port=int(os.getenv("DASHBOARD_PORT", "8087")),
            username=os.getenv("API_USERNAME", ""),
            password=os.getenv("API_PASSWORD", ""),
            jwt_secret=os.getenv("API_JWT_SECRET", ""),
        ),
        model=ModelSettings(
            model_name=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
            base_url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
            validation_mode=os.getenv("VALIDATION_MODE", "real").lower(),
        ),
        risk=RiskSettings(),
        trading=TradingSettings(
            dry_run=os.getenv("DRY_RUN", "true").lower() == "true",
            wallet_size=float(os.getenv("INITIAL_CAPITAL", "10000.0")),
            stake_currency=os.getenv("CAPITAL_CURRENCY", "USDT"),
        ),
        news=NewsSettings(),
        paths=PathSettings(),
    )


# Singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings
