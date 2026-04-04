# Testing Rules — AI Quantitative Trader V6.0

## Framework
- `pytest` come test runner principale
- `pytest-asyncio` per test asincroni
- `unittest.mock` per mocking (preferire `MagicMock` e `AsyncMock`)

## Convenzioni
- File test: `tests/test_{modulo}.py`
- Funzioni test: `test_{cosa_testa}_{condizione}_{risultato_atteso}`
- Fixtures in `conftest.py`
- Mock TUTTE le chiamate API esterne nei test

## Copertura Minima
- Moduli `ai/`: 80% coverage
- Moduli `risk/`: 90% coverage
- Moduli `memory/`: 70% coverage
- Utility functions: 60% coverage

## Test Categories
```python
# Unit test — singola funzione isolata
def test_calculate_pnl_positive_trade():
    result = calculate_pnl(Decimal("50000"), Decimal("52000"), Decimal("0.1"))
    assert result == Decimal("200")

# Integration test — moduli che interagiscono
async def test_decision_engine_with_risk_gate():
    decision = await engine.evaluate(mock_market_data)
    filtered = risk_gate.filter(decision)
    assert filtered.confidence <= decision.confidence

# Regression test — bug specifico risolto
def test_float_precision_bug_v3():
    """Regression: V3 aveva errori di precisione con float."""
    result = calculate_pnl(Decimal("0.1"), Decimal("0.3"), Decimal("1"))
    assert result == Decimal("0.2")  # float: 0.19999999...
```

## Anti-patterns
- ❌ Test che dipendono dall'ordine di esecuzione
- ❌ Test che chiamano API reali
- ❌ Test senza asserzioni
- ❌ Test che testano l'implementazione invece del comportamento
