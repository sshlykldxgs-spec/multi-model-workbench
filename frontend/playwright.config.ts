import { defineConfig } from 'playwright';

/**
 * 端到端烟雾测试配置。
 * 蓝图第 10 节：前端门禁需要类型检查、代码检查和基本的端到端烟雾测试。
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  use: { baseURL: 'http://localhost:5173', trace: 'on-first-retry' },
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
  },
});
