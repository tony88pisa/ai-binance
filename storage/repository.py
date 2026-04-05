import sqlite3
import json
from typing import Dict, Any, List
from datetime import datetime, timezone
import os
from pathlib import Path

# Path assoluti centrati sulla cartella storage
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "storage" / "v8_platform.sqlite"
SCHEMA_PATH = PROJECT_ROOT / "storage" / "schema.sql"

class Repository:
    def __init__(self):
        self.db_path = str(DB_PATH)
        self.schema_path = str(SCHEMA_PATH)
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _migrate_db(self, conn):
        cur = conn.cursor()
        
        # market_data migration
        cur.execute("PRAGMA table_info(market_data)")
        md_cols = [r['name'] for r in cur.fetchall()]
        if 'symbol' in md_cols and 'asset' not in md_cols:
            try: conn.execute("ALTER TABLE market_data RENAME COLUMN symbol TO asset")
            except: pass
            
        cur.execute("PRAGMA table_info(market_data)")
        md_cols = [r['name'] for r in cur.fetchall()]
        req_md = {
            "rsi_5m": "REAL", "rsi_1h": "REAL", "macd_5m": "REAL", "macd_1h": "REAL", 
            "atr_5m": "REAL", "decision": "TEXT", "confidence": "INTEGER", 
            "regime": "TEXT", "consensus_score": "REAL", "position_size_pct": "REAL", 
            "atr_stop_distance": "REAL", "why_not_trade": "TEXT"
        }
        for col, typ in req_md.items():
            if col not in md_cols:
                conn.execute(f"ALTER TABLE market_data ADD COLUMN {col} {typ}")
        
        # service_state migration
        cur.execute("PRAGMA table_info(service_state)")
        ss_cols = [r['name'] for r in cur.fetchall()]
        if 'service_name' in ss_cols and 'service' not in ss_cols:
            try: conn.execute("ALTER TABLE service_state RENAME COLUMN service_name TO service")
            except: pass
        if 'config_json' in ss_cols and 'state_json' not in ss_cols:
            try: conn.execute("ALTER TABLE service_state RENAME COLUMN config_json TO state_json")
            except: pass
            
        cur.execute("PRAGMA table_info(service_state)")
        ss_cols = [r['name'] for r in cur.fetchall()]
        if 'state_json' not in ss_cols:
            try: conn.execute("ALTER TABLE service_state ADD COLUMN state_json TEXT DEFAULT '{}'")
            except: pass
        if 'status' not in ss_cols:
             try: conn.execute("ALTER TABLE service_state ADD COLUMN status TEXT DEFAULT 'active'")
             except: pass
            
        # decisions migration
        cur.execute("PRAGMA table_info(decisions)")
        columns = [row['name'] for row in cur.fetchall()]
        
        if 'timestamp_utc' in columns and 'timestamp' not in columns:
            try: conn.execute("ALTER TABLE decisions RENAME COLUMN timestamp_utc TO timestamp")
            except: pass
        if 'position_size' in columns and 'size_pct' not in columns:
            try: conn.execute("ALTER TABLE decisions RENAME COLUMN position_size TO size_pct")
            except: pass
        if 'market_regime' in columns and 'regime' not in columns:
            try: conn.execute("ALTER TABLE decisions RENAME COLUMN market_regime TO regime")
            except: pass
            
        cur.execute("PRAGMA table_info(decisions)")
        columns = [row['name'] for row in cur.fetchall()]
        
        if 'size_pct' not in columns:
            try: conn.execute("ALTER TABLE decisions ADD COLUMN size_pct REAL DEFAULT 0.0")
            except: pass
        if 'entry_price' not in columns:
            try: conn.execute("ALTER TABLE decisions ADD COLUMN entry_price REAL DEFAULT 0.0")
            except: pass
        if 'atr_stop_distance' not in columns:
            try: conn.execute("ALTER TABLE decisions ADD COLUMN atr_stop_distance REAL DEFAULT 0.0")
            except: pass
        if 'status' not in columns:
            try: conn.execute("ALTER TABLE decisions ADD COLUMN status TEXT DEFAULT 'OPEN'")
            except: pass
        if 'exchange_order_id' not in columns:
            try: conn.execute("ALTER TABLE decisions ADD COLUMN exchange_order_id TEXT")
            except: pass
        if 'inner_monologue' not in columns:
            try: conn.execute("ALTER TABLE decisions ADD COLUMN inner_monologue TEXT")
            except: pass
        if 'agent_name' not in columns:
            try: conn.execute("ALTER TABLE decisions ADD COLUMN agent_name TEXT")
            except: pass
            
        conn.commit()

    def _init_db(self):
        schema_file = Path(self.schema_path)
        if not schema_file.exists():
            raise FileNotFoundError(f"Schema SQL mancante al percorso obbligatorio: {schema_file}")
            
        if not DB_PATH.parent.exists():
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            
        with self._conn() as conn:
            with open(schema_file, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
            self._migrate_db(conn)

    def upsert_market_snapshot(self, data: Dict[str, Any]):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO market_data 
                (asset, price, rsi_5m, rsi_1h, macd_5m, macd_1h, atr_5m, 
                decision, confidence, regime, consensus_score, position_size_pct, 
                atr_stop_distance, why_not_trade, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset) DO UPDATE SET
                price=excluded.price, rsi_5m=excluded.rsi_5m, rsi_1h=excluded.rsi_1h,
                macd_5m=excluded.macd_5m, macd_1h=excluded.macd_1h, atr_5m=excluded.atr_5m,
                decision=excluded.decision, confidence=excluded.confidence, regime=excluded.regime,
                consensus_score=excluded.consensus_score, position_size_pct=excluded.position_size_pct,
                atr_stop_distance=excluded.atr_stop_distance, why_not_trade=excluded.why_not_trade,
                updated_at=excluded.updated_at
            """, (
                data["asset"], data["price"], data["rsi_5m"], data["rsi_1h"], data["macd_5m"],
                data["macd_1h"], data["atr_5m"], data["decision"], data["confidence"],
                data["regime"], data["consensus_score"], data["position_size_pct"],
                data["atr_stop_distance"], data["why_not_trade"], datetime.now(timezone.utc).isoformat()
            ))
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO market_history (asset, price, rsi_5m, macd_5m, decision, confidence, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (data["asset"], data["price"], data["rsi_5m"], data["macd_5m"], 
                  data["decision"], data["confidence"], datetime.now(timezone.utc).isoformat()))
            conn.commit()

    def get_market_history(self, asset: str, limit: int = 100) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM market_history WHERE asset=? ORDER BY timestamp DESC LIMIT ?", (asset, limit)).fetchall()
            return [dict(r) for r in rows]

    def get_latest_snapshot(self, asset: str) -> Dict[str, Any]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM market_data WHERE asset=?", (asset,)).fetchone()
            return dict(row) if row else {}

    def get_latest_snapshots(self) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM market_data ORDER BY asset ASC").fetchall()
            return [dict(r) for r in rows]

    def save_trade_decision(self, data: Dict[str, Any]):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO decisions (id, asset, action, confidence, size_pct, thesis, regime, timestamp, entry_price, atr_stop_distance, status, inner_monologue, agent_name, exchange_order_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (data["id"], data["asset"], data["action"], data["confidence"],
                  data["size_pct"], data["thesis"], data["regime"], datetime.now(timezone.utc).isoformat(),
                  data.get("entry_price", 0.0), data.get("atr_stop_distance", 0.0), data.get("status", "OPEN"),
                  data.get("inner_monologue", ""), data.get("agent_name", "Alpha-Sentinel"), data.get("exchange_order_id", None)))
            conn.commit()

    def get_open_decisions(self) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT d.* FROM decisions d
                LEFT JOIN trade_outcomes o ON d.id = o.decision_id
                WHERE (d.status = 'OPEN' OR d.status = 'CLOSING' OR d.status = 'PENDING')
                AND o.id IS NULL
            """).fetchall()
            return [dict(r) for r in rows]

    def update_decision_status(self, decision_id: str, status: str):
        with self._conn() as conn:
            conn.execute("UPDATE decisions SET status = ? WHERE id = ?", (status, decision_id))
            conn.commit()

    def get_stale_decisions(self, max_age_hours: int = 24) -> List[Dict[str, Any]]:
        """Find trades that have been open for too long without completion."""
        with self._conn() as conn:
            rows = conn.execute(f"""
                SELECT * FROM decisions 
                WHERE status IN ('OPEN', 'PENDING', 'CLOSING')
                AND timestamp < datetime('now', '-{max_age_hours} hour')
            """).fetchall()
            return [dict(r) for r in rows]

    def close_trade_with_outcome(self, outcome_data: Dict[str, Any]):
        with self._conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO trade_outcomes (id, decision_id, realized_pnl_pct, was_profitable, closed_at)
                VALUES (?, ?, ?, ?, ?)
            """, (outcome_data["id"], outcome_data["decision_id"], outcome_data["realized_pnl_pct"],
                  outcome_data["was_profitable"], datetime.now(timezone.utc).isoformat()))
            
            conn.execute("UPDATE decisions SET status = 'CLOSED' WHERE id = ?", (outcome_data["decision_id"],))
            conn.commit()

    def save_trade_outcome(self, data: Dict[str, Any]):
        """Standalone outcome save (called by squad_crypto compound wallet).
        Creates a synthetic decision_id if none exists."""
        import uuid as _uuid
        outcome_id = f"OUT-{_uuid.uuid4().hex[:8]}"
        decision_id = data.get("decision_id", f"SYNTH-{_uuid.uuid4().hex[:8]}")
        with self._conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO trade_outcomes (id, decision_id, realized_pnl_pct, was_profitable, closed_at)
                VALUES (?, ?, ?, ?, ?)
            """, (outcome_id, decision_id, data.get("pnl_pct", 0.0),
                  1 if data.get("was_profitable") else 0,
                  datetime.now(timezone.utc).isoformat()))
            conn.commit()

    def get_outcomes_with_details(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent outcomes with decision details for Dream Agent analysis."""
        with self._conn() as conn:
            rows = conn.execute(f"""
                SELECT o.realized_pnl_pct, o.was_profitable, o.closed_at,
                       d.asset, d.action, d.entry_price, d.confidence, d.regime,
                       d.agent_name, d.thesis, d.size_pct
                FROM trade_outcomes o
                LEFT JOIN decisions d ON o.decision_id = d.id
                WHERE o.closed_at > datetime('now', '-{days} day')
                ORDER BY o.closed_at DESC
            """).fetchall()
            return [dict(r) for r in rows]

    def save_skill_candidate(self, skill: Dict[str, Any]):
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO skill_candidates (skill_id, name, version, status, skill_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (skill["skill_id"], skill["name"], skill["version"], skill["validation_status"],
                  json.dumps(skill), skill["created_at"]))
            conn.commit()

    def list_skill_candidates(self) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM skill_candidates ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def save_skill_validation(self, skill_id: str, metrics: Dict[str, Any]):
        with self._conn() as conn:
            passed = 1 if metrics["passed"] else 0
            conn.execute("""
                INSERT INTO skill_validations (skill_id, passed, win_rate, max_drawdown, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (skill_id, passed, metrics["win_rate"], metrics["max_drawdown"],
                  metrics["reason"], datetime.now(timezone.utc).isoformat()))
            conn.execute("UPDATE skill_candidates SET status=? WHERE skill_id=?", 
                         ("approved" if passed else "rejected", skill_id))
            conn.commit()

    def save_skill_promotion(self, skill_id: str, reason: str):
        with self._conn() as conn:
            conn.execute("INSERT INTO skill_promotions (skill_id, reason, promoted_at) VALUES (?, ?, ?)",
                         (skill_id, reason, datetime.now(timezone.utc).isoformat()))
            conn.execute("UPDATE skill_candidates SET status='promoted' WHERE skill_id=?", (skill_id,))
            conn.commit()

    def update_service_heartbeat(self, service: str, state_json: str):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO service_state (service, status, last_heartbeat, state_json)
                VALUES (?, 'active', ?, ?) ON CONFLICT(service) DO UPDATE SET
                last_heartbeat=excluded.last_heartbeat, state_json=excluded.state_json, status='active'
            """, (service, datetime.now(timezone.utc).isoformat(), state_json))
            conn.commit()

    def update_service_state(self, service: str, status: str, pid: int, state_data: Dict[str, Any]):
        """Legacy compatibility for evolution_loop."""
        state_data["pid"] = pid
        state_data["status_detail"] = status
        self.update_service_heartbeat(service, json.dumps(state_data))

    def log_nvidia_review(self, review: Dict[str, Any]):
        """Saves detailed AI assessment log."""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO supervisor_logs (timestamp, ai_assessment, actions_taken)
                VALUES (?, ?, ?)
            """, (
                datetime.now(timezone.utc).isoformat(),
                json.dumps(review.get("regime_findings", "N/A")),
                f"Review ID: {review.get('review_id')} | Candidates: {len(review.get('candidate_strategies', []))}"
            ))
            conn.commit()

    def get_service_state(self, service: str) -> Dict[str, Any]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM service_state WHERE service=?", (service,)).fetchone()
            return dict(row) if row else {}

    def get_recent_outcomes(self, days: int) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(f"SELECT * FROM trade_outcomes WHERE closed_at > datetime('now', '-{days} day') ORDER BY closed_at ASC").fetchall()
            return [dict(r) for r in rows]

    def get_recent_decisions(self, days: int) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(f"SELECT * FROM decisions WHERE timestamp > datetime('now', '-{days} day')").fetchall()
            return [dict(r) for r in rows]

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT o.realized_pnl_pct, o.was_profitable, o.closed_at,
                       d.asset, d.action, d.entry_price, d.size_pct
                FROM trade_outcomes o
                JOIN decisions d ON o.decision_id = d.id
                WHERE d.entry_price > 0 AND ABS(o.realized_pnl_pct) < 5.0
                ORDER BY o.closed_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # --- AI SUPERVISOR METHODS ---
    def get_supervisor_controls(self) -> Dict[str, Any]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM supervisor_controls WHERE id = 1").fetchone()
            if not row:
                # Seed default
                self.update_supervisor_controls({
                    "emergency_stop": 0, "max_open_trades": 3, "min_confidence": 70,
                    "close_losers_threshold": -5.0, "regime_filter_active": 1,
                    "ai_reasoning": "Initial default settings."
                })
                row = conn.execute("SELECT * FROM supervisor_controls WHERE id = 1").fetchone()
            return dict(row)

    def update_supervisor_controls(self, data: Dict[str, Any]):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO supervisor_controls (id, emergency_stop, max_open_trades, min_confidence, close_losers_threshold, regime_filter_active, last_update, ai_reasoning)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                emergency_stop=excluded.emergency_stop, max_open_trades=excluded.max_open_trades,
                min_confidence=excluded.min_confidence, close_losers_threshold=excluded.close_losers_threshold,
                regime_filter_active=excluded.regime_filter_active, last_update=excluded.last_update,
                ai_reasoning=excluded.ai_reasoning
            """, (
                data.get("emergency_stop", 0), data.get("max_open_trades", 3),
                data.get("min_confidence", 70), data.get("close_losers_threshold", -5.0),
                data.get("regime_filter_active", 1), datetime.now(timezone.utc).isoformat(),
                data.get("ai_reasoning", "")
            ))
            conn.commit()

    def add_supervisor_log(self, wallet_state: str, assessment: str, actions: str):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO supervisor_logs (timestamp, wallet_state, ai_assessment, actions_taken)
                VALUES (?, ?, ?, ?)
            """, (datetime.now(timezone.utc).isoformat(), wallet_state, assessment, actions))
            conn.commit()

    def get_supervisor_logs(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM supervisor_logs ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    # --- LIVE ACTIVITY FEED ---
    def _ensure_activity_table(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def log_activity(self, agent: str, action: str, detail: str = ""):
        """Log a real-time activity event from any agent for the live dashboard feed."""
        self._ensure_activity_table()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO agent_activity (timestamp, agent, action, detail) VALUES (?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), agent, action, detail)
            )
            # Keep only last 500 entries to avoid table bloat
            conn.execute("DELETE FROM agent_activity WHERE id NOT IN (SELECT id FROM agent_activity ORDER BY id DESC LIMIT 500)")
            conn.commit()

    def get_recent_activity(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Get the most recent agent activity for the live dashboard feed."""
        self._ensure_activity_table()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_activity ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

