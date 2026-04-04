Genera un commit convenzionale:
1. Analizza i file staged con `git diff --cached`
2. Determina il tipo di change: feat/fix/refactor/docs/test/chore
3. Genera un messaggio commit descrittivo seguendo Conventional Commits
4. Includi scope se applicabile (ai, risk, memory, telemetry, dashboard)

Formato: `{type}({scope}): {description}`

Esempi:
- `feat(ai): add fallback parser for qwen3 JSON output`
- `fix(risk): correct circuit breaker threshold calculation`
- `refactor(memory): migrate to UUID-linked decision records`
