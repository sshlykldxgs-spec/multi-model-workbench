import { expect, test } from '@playwright/test';

/**
 * P0 验收的自动化版本（蓝图第 11 节 P0）：
 *   打开前端页面，选 mock 模型发一句话，**看到逐字输出**。
 *
 * 关于"逐字"这项断言：单纯 toContainText 无法证明流式 ——
 * 后端一次返回整段也会通过。所以这里改成**采样气泡文本**，
 * 要求观察到多个长度递增的中间态，即最终文本的真前缀。
 */

/** mock 回复的结尾，用于判定流已完成。 */
const REPLY_TAIL = '接入真实模型后';

test('@smoke 登录后能用 mock 模型看到逐字输出', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('邮箱').fill('admin@example.com');
  await page.getByLabel('密码').fill('admin12345');
  await page.getByRole('button', { name: '登录' }).click();

  // 登录后进入工作区。
  // 注意：站点名在工作区是 <span>，不是 heading（只有登录页才有 <h1>），
  // 所以这里断言导航链接而不是 getByRole('heading')。
  await expect(page.getByRole('link', { name: '工作区' })).toBeVisible();

  const box = page.getByPlaceholder('输入消息，Enter 发送，Shift+Enter 换行');
  await box.fill('你好');
  await page.getByRole('button', { name: '发送' }).click();

  // 助手气泡是唯一带 whitespace-pre-wrap 的（用户气泡没有这个类）
  const bubble = page.locator('div.whitespace-pre-wrap').first();
  await expect(bubble).toBeVisible({ timeout: 10_000 });

  // 采样：每 20ms 读一次文本，记录每次变化（与 mock 的 2 字 / 20ms 节奏对齐）
  const snapshots: string[] = [];
  let last = '';
  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    const text = (await bubble.textContent()) ?? '';
    if (text !== last) {
      snapshots.push(text);
      last = text;
    }
    if (text.includes(REPLY_TAIL)) break;
    await page.waitForTimeout(20);
  }

  const final = snapshots.at(-1) ?? '';

  // 1) 回复完整到达
  expect(final).toContain('mock 模型');
  expect(final).toContain('你好');
  expect(final).toContain(REPLY_TAIL);

  // 2) 确实逐字：观察到 >=3 个中间态，且至少一个是最终文本的真前缀
  expect(snapshots.length).toBeGreaterThanOrEqual(3);
  const increasing = snapshots.filter(
    (s, i) => i > 0 && s.length > snapshots[i - 1].length,
  );
  expect(increasing.length).toBeGreaterThanOrEqual(2);
  const sawPartial = snapshots.some(
    (s) => s.length > 0 && s !== final && final.startsWith(s),
  );
  expect(sawPartial, '没有观察到任何中间态 —— 说明回复是一次性返回的，不是流式').toBe(true);

  // 3) 费用与上游模型已展示
  await expect(page.getByText(/上游模型/)).toBeVisible();
});
