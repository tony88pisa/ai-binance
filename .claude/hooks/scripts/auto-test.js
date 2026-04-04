/**
 * Auto-test Hook
 * Esegue automaticamente i test rilevanti dopo ogni modifica di file Python.
 */
const { execSync } = require('child_process');
const path = require('path');

const TEST_MAP = {
  'ai/': 'tests/test_ai.py',
  'risk/': 'tests/',
  'memory/': 'tests/',
  'services/': 'tests/',
  'scheduler/': 'tests/',
};

function getTestTarget(changedFile) {
  for (const [srcDir, testTarget] of Object.entries(TEST_MAP)) {
    if (changedFile.includes(srcDir)) {
      return testTarget;
    }
  }
  return null;
}

function runTests(testTarget, cwd) {
  try {
    const result = execSync(
      `python -m pytest ${testTarget} -x --tb=short -q 2>&1`,
      { cwd, timeout: 30000, encoding: 'utf-8' }
    );
    return { success: true, output: result };
  } catch (error) {
    return { success: false, output: error.stdout || error.message };
  }
}

module.exports = { getTestTarget, runTests };
