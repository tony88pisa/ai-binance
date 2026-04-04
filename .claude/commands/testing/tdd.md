Esegui test TDD per il file o modulo specificato:
1. Identifica il file target: $ARGUMENTS
2. Trova o crea il file di test corrispondente
3. Se il test non esiste, crealo con casi base
4. Esegui i test con pytest
5. Se falliscono, analizza e suggerisci fix
6. Ripeti fino a tutti verdi

Convenzione test:
- File: `tests/test_{modulo}.py`
- Prefisso: `test_`
- Usa fixtures pytest
- Mock le chiamate API esterne
- Usa `pytest-asyncio` per test asincroni
