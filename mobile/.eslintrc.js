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
    'react-hooks/exhaustive-deps': 'error',
    'react-hooks/set-state-in-effect': 'error',
    'react-hooks/refs': 'error',
    'react-hooks/purity': 'error',
    'react-hooks/immutability': 'error',
  },
  ignorePatterns: [
    'node_modules/',
    '.expo/',
    '.expo-shared/',
    'dist/',
    'build/',
  ],
};
