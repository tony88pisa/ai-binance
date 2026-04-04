/**
 * Secret Scanner Hook
 * Previene il commit di API keys, password e secrets nel codice.
 * Eseguito pre-commit per bloccare leak accidentali.
 */
const PATTERNS = [
  /(?:api[_-]?key|apikey)\s*[:=]\s*['"][A-Za-z0-9]{20,}/gi,
  /(?:secret|password|passwd|pwd)\s*[:=]\s*['"][^'"]{8,}/gi,
  /(?:BINANCE|BITGET|BYBIT)_[A-Z_]*(?:KEY|SECRET)\s*=\s*['"][^'"]+/gi,
  /(?:sk-|pk-|rk-)[A-Za-z0-9]{20,}/g,
  /(?:ghp_|gho_|ghs_)[A-Za-z0-9]{36,}/g,
  /-----BEGIN (?:RSA )?PRIVATE KEY-----/g,
  /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/g, // JWT
];

const ALLOWLIST = [
  '.env.example',
  'test_',
  'mock_',
  '__pycache__',
  '.git/',
];

function isAllowlisted(filepath) {
  return ALLOWLIST.some(p => filepath.includes(p));
}

async function scanFile(filepath, content) {
  if (isAllowlisted(filepath)) return [];
  
  const findings = [];
  const lines = content.split('\n');
  
  for (let i = 0; i < lines.length; i++) {
    for (const pattern of PATTERNS) {
      pattern.lastIndex = 0;
      if (pattern.test(lines[i])) {
        findings.push({
          file: filepath,
          line: i + 1,
          pattern: pattern.source.substring(0, 40),
          severity: 'CRITICAL'
        });
      }
    }
  }
  
  return findings;
}

module.exports = { scanFile, PATTERNS };
