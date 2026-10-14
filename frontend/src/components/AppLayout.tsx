import { useEffect, useState } from 'react';
import { Link, Outlet, useNavigate } from 'react-router-dom';

import { api, ApiError, type MeResponse } from '../api/client';

/**
 * 工作区外壳。
 *
 * 蓝图 5A：产品分工作区（用）与配置区（设计）两个区域，入口与状态分开。
 * P0 只做工作区；配置区在 P5，路由前缀 /studio，此处先放一个禁用入口占位。
 */
export function AppLayout() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    api
      .me()
      .then((user) => {
        if (!cancelled) setMe(user);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.code === 'unauthorized') {
          navigate('/login', { replace: true });
          return;
        }
        setError(err instanceof ApiError ? err.friendly : '加载失败');
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  if (checking) {
    // 空状态与加载中必须显式处理（frontend/AGENTS.md 第 6 节）
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-gray-500">
        正在加载…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3">
        <p className="text-sm text-red-600">{error}</p>
        <button
          className="rounded border px-3 py-1 text-sm"
          onClick={() => window.location.reload()}
        >
          重试
        </button>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-4">
          <span className="font-semibold">多模型工作台</span>
          <nav className="flex gap-3 text-sm">
            <Link to="/" className="text-gray-700 hover:underline">
              工作区
            </Link>
            {/* 配置区在 P5；此处显式标注而不是藏起来，避免用户以为功能丢了 */}
            <span className="cursor-not-allowed text-gray-300" title="配置区在 P5 交付">
              配置区（P5）
            </span>
          </nav>
        </div>
        <div className="flex items-center gap-3 text-sm text-gray-600">
          {me?.email ? <span>{me.email}</span> : null}
          {me?.role ? (
            <span className="rounded bg-gray-100 px-2 py-0.5 text-xs">
              {me.role === 'admin' ? '管理员' : '成员'}
            </span>
          ) : null}
          <button
            className="rounded border px-2 py-1 text-xs"
            onClick={() => {
              void api.logout().then(() => navigate('/login', { replace: true }));
            }}
          >
            退出
          </button>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
