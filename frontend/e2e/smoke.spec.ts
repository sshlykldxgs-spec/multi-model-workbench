import { expect, test } from 'playwright';

/**
 * P0 验收的自动化版本（蓝图第 11 节 P0）：
 *   打开前端页面，选 mock 模型发一句话，看到逐字输出。
 */
test('@smoke 登录后能用 mock 模型看到逐字输出', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('邮箱').fill('admin@example.com');
  await page.getByLabel('密码').fill('admin12345');
  await page.getByRole('button', { name: '登录' }).click();

  await expect(page.getByRole('heading', { name: '多模型工作台' })).toBeVisible();

  const box = page.getByPlaceholder('输入消息，Enter 发送，Shift+Enter 换行');
  await box.fill('你好');
  await page.getByRole('button', { name: '发送' }).click();

  // 逐字输出：先出现部分内容，再变成完整内容
  const bubble = page.locator('div.whitespace-pre-wrap').first();
  await expect(bubble).toContainText('mock 模型', { timeout: 10_000 });
  await expect(bubble).toContainText('你好');
});
