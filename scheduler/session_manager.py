import logging
from datetime import datetime, time as dt_time

logger = logging.getLogger("scheduler")

# Finestra LAB configurabile: 02:00 - 03:00 locale
LAB_START = dt_time(2, 0)
LAB_END = dt_time(3, 0)

def current_mode() -> str:
    """Ritorna LIVE_MODE o LAB_MODE dipendente dall'ora locale. Il mercato crypto è 24/7."""
    now = datetime.now().time()
    if LAB_START <= now < LAB_END:
        return "LAB_MODE"
    return "LIVE_MODE"

def should_run_lab_cycle() -> bool:
    return current_mode() == "LAB_MODE"

def should_run_live_cycle() -> bool:
    return current_mode() == "LIVE_MODE"
