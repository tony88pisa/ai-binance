# Regole di Sicurezza — AI Quantitative Trader V6.0

## Secrets Management
- MAI hardcodare API keys, password, token nel codice
- Tutti i secrets devono essere in `.env` e caricati via `os.getenv()` o `python-dotenv`
- `.env` DEVE essere nel `.gitignore`
- I log NON devono mai contenere API keys o secrets
- Usare `settings.py` con `validate_and_report()` per configurazione

## API Security
- Tutte le API keys Binance/Bitget devono avere IP whitelist
- Usare permessi minimi necessari (no withdrawal permission se non necessario)
- Rate limiting implementato su tutte le chiamate API
- Timeout configurato su ogni chiamata HTTP

## Error Handling
- MAI esporre stack trace completi all'utente
- Loggare errori con contesto ma senza dati sensibili
- Circuit breaker su tutti i servizi esterni

## Data Protection
- SQLite database non deve contenere credenziali
- File con dati sensibili: permessi 600 (owner-only)
- Backup devono essere criptati se contengono dati finanziari
