// ESLint 扁平配置。
//
// 缺陷记录：原配置只用了 @eslint/js，没有 TypeScript 解析器，
// 导致 src/ 下 6 个 .ts/.tsx 文件全部 "Parsing error" ——
// 也就是说 lint 这道门禁从写下起就没真正生效过。
//
// 用 typescript-eslint 的 recommended 规则集：它同时提供解析器与规则，
// 且是扁平配置（flat config）的一等公民，不需要额外拼 parser + plugin。

import js from '@eslint/js';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    // dist 是构建产物；schema.d.ts 由 OpenAPI 生成，不该被 lint
    ignores: ['dist/**', 'node_modules/**', 'src/api/schema.d.ts'],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        ...globals.browser,
      },
    },
    rules: {
      // 未使用变量：允许 _ 前缀的占位参数
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
    },
  },
  {
    files: ['e2e/**/*.ts', '*.config.ts'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        ...globals.node,
      },
    },
  },
);
