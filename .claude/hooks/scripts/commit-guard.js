/**
 * Commit Guard Hook
 * Valida i commit prima di procedere:
 * - Formato messaggio (Conventional Commits)
 * - Nessun file grande (>5MB)
 * - Nessun file binario accidentale
 */
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

const BLOCKED_EXTENSIONS = [
  '.exe', '.dll', '.so', '.dylib',
  '.sqlite', '.db',
  '.zip', '.tar', '.gz', '.rar',
  '.mp4', '.mp3', '.avi',
  '.psd', '.ai',
];

const COMMIT_PATTERN = /^(feat|fix|refactor|docs|test|chore|perf|ci|build|style)(\([a-z-]+\))?: .{3,72}$/;

function validateCommitMessage(message) {
  const firstLine = message.split('\n')[0];
  if (!COMMIT_PATTERN.test(firstLine)) {
    return {
      valid: false,
      reason: `Commit message non segue Conventional Commits: "${firstLine}"\nFormato: type(scope): description`
    };
  }
  return { valid: true };
}

function checkFile(filepath, size) {
  const ext = filepath.substring(filepath.lastIndexOf('.'));
  
  if (BLOCKED_EXTENSIONS.includes(ext.toLowerCase())) {
    return { blocked: true, reason: `File binario bloccato: ${ext}` };
  }
  
  if (size > MAX_FILE_SIZE) {
    return { blocked: true, reason: `File troppo grande: ${(size / 1024 / 1024).toFixed(1)}MB > 5MB` };
  }
  
  return { blocked: false };
}

module.exports = { validateCommitMessage, checkFile, COMMIT_PATTERN };
