Analizza il codebase per vulnerabilità di sicurezza:
1. Scansiona per API keys o secrets hardcoded
2. Verifica che `.env` sia nel `.gitignore`
3. Controlla che i log non espongano dati sensibili
4. Verifica le dipendenze per vulnerabilità note
5. Controlla i permessi file per dati sensibili

Usa l'agent `security-auditor` per un audit completo.
Output: report con severity (CRITICAL/HIGH/MEDIUM/LOW) per ogni finding.
