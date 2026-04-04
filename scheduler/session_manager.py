import logging
from datetime import datetime, time as dt_time

logger = logging.getLogger("scheduler")

# Finestra LAB configurabile: Primi 20 minuti di ogni ora
def current_mode() -> str:
    """Ritorna 'LAB_MODE' o 'LIVE_MODE' basandosi sull'ora locale.
    LAB_MODE: Primi 20 minuti di ogni ora.
    LIVE_MODE: Resto dell'ora.
    """
    now_m = datetime.now().minute
    if 0 <= now_m < 55:
        return "LAB_MODE"
    return "LIVE_MODE"

def should_run_lab_cycle() -> bool:
    return current_mode() == "LAB_MODE"

def should_run_live_cycle() -> bool:
    return current_mode() == "LIVE_MODE"
