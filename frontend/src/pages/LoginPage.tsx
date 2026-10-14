import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api, ApiError } from '../api/client';

export function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const navigate = useNavigate();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      await api.login(email, password);
      navigate('/', { replace: true });
    } catch (err) {
      // 错误提示必须是人话（frontend/AGENTS.md 第 6 节）
      setError(err instanceof ApiError ? err.friendly : '登录失败，请稍后重试。');
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm space-y-4 rounded-lg border bg-white p-6 shadow-sm"
      >
        <div>
          <h1 className="text-lg font-semibold">多模型工作台</h1>
          <p className="mt-1 text-xs text-gray-500">小团队内部使用，账号由管理员邀请开通</p>
        </div>

        <label className="block text-sm">
          <span className="text-gray-700">邮箱</span>
          <input
            type="email"
            required
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded border px-3 py-2 text-sm"
          />
        </label>

        <label className="block text-sm">
          <span className="text-gray-700">密码</span>
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded border px-3 py-2 text-sm"
          />
        </label>

        {error ? (
          <p role="alert" className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={pending}
          className="w-full rounded bg-gray-900 px-3 py-2 text-sm text-white disabled:opacity-50"
        >
          {pending ? '登录中…' : '登录'}
        </button>
      </form>
    </div>
  );
}
