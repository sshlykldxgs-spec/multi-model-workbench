// 必须从 @playwright/test 导入：playwright 包只导出浏览器驱动
// （chromium/firefox/webkit 等），不含测试运行器。
// 实测用 'playwright' 会直接报 does not provide an export named 'defineConfig'。
import { defineConfig } from '@playwright/test';

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
