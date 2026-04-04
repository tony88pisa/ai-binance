# Coding Style — AI Quantitative Trader V6.0

## Python Standards
- Python 3.12+ con type hints obbligatori
- Seguire PEP 8 con line length max 120
- Usare `Decimal` per TUTTI i calcoli finanziari (MAI `float`)
- Usare `dataclasses` o `pydantic` per modelli dati
- Import ordinati: stdlib → third-party → local (isort compatibile)

## Naming Conventions
- `snake_case` per variabili e funzioni
- `PascalCase` per classi
- `UPPER_CASE` per costanti
- Prefisso `_` per metodi/variabili private
- Prefisso `is_/has_/can_` per booleani

## Logging
- Usare `logging` module, MAI `print()`
- Logger per modulo: `logger = logging.getLogger(__name__)`
- Livelli: DEBUG per dettagli, INFO per operazioni, WARNING per anomalie, ERROR per errori

## Error Handling
```python
# ✅ CORRETTO
try:
    result = await exchange.fetch_ticker(pair)
except ccxt.NetworkError as e:
    logger.error("Network error fetching %s: %s", pair, e)
    raise
except ccxt.ExchangeError as e:
    logger.error("Exchange error for %s: %s", pair, e)
    return None

# ❌ SBAGLIATO
try:
    result = exchange.fetch_ticker(pair)
except:
    pass
```

## Async
- Usare `asyncio` per I/O bound operations
- Non bloccare mai l'event loop con operazioni sync pesanti
- Usare `asyncio.gather()` per operazioni concorrenti
