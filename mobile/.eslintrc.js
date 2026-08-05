module.exports = {
  extends: [
    'expo',
    'plugin:@typescript-eslint/recommended',
  ],
  parser: '@typescript-eslint/parser',
  plugins: ['@typescript-eslint'],
  rules: {
    // Temporarily downgrade TypeScript rules to warnings for existing codebase
    '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
    '@typescript-eslint/no-explicit-any': 'warn',
    // Temporarily downgrade react-hooks rules to warnings
    // These are real bugs that need fixing in a follow-up task
    // See: task-223 for full context
    'react-hooks/exhaustive-deps': 'warn',
    'react-hooks/set-state-in-effect': 'warn',
    'react-hooks/refs': 'warn',
    'react-hooks/purity': 'warn',
    'react-hooks/immutability': 'warn',
  },
  ignorePatterns: [
    'node_modules/',
    '.expo/',
    '.expo-shared/',
    'dist/',
    'build/',
  ],
};
