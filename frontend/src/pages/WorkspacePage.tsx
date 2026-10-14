import { useEffect, useMemo, useRef, useState } from 'react';

import { api, ApiError, startRun, type ModelInfo } from '../api/client';

/**
 * 工作区。
 *
 * P0 验收标准（蓝图第 11 节 P0）：选 mock 模型发一句话，看到逐字输出。
 * 所以这个页面的核心是流式渲染。
 */

interface Turn {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  streaming?: boolean;
  cost?: number;
  upstreamModel?: string;
}

export function WorkspacePage() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [modelId, setModelId] = useState<string>('');
  const [input, setInput] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [connState, setConnState] = useState<'idle' | 'streaming' | 'done' | 'lost'>('idle');
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    api
      .models()
      .then((res) => {
        setModels(res.items);
        // 默认选中 mock，让 P0 的验收路径最短
        const preferred = res.items.find((m) => m.id === 'mock-echo') ?? res.items[0];
        if (preferred) setModelId(preferred.id);
      })
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.friendly : '模型列表加载失败');
      });
  }, []);

  const selected = useMemo(
    () => models.find((m) => m.id === modelId) ?? null,
    [models, modelId],
  );

  async function onSend() {
    const text = input.trim();
    if (!text || !selected || running) return;

    setError(null);
    setInput('');
    const userTurn: Turn = { id: crypto.randomUUID(), role: 'user', text };
    const assistantId = crypto.randomUUID();
    setTurns((prev) => [
      ...prev,
      userTurn,
      { id: assistantId, role: 'assistant', text: '', streaming: true },
    ]);
    setRunning(true);
    setConnState('streaming');

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await startRun(
        'local', // P0 会话未持久化；P1 起用真实会话 ID
        { model_id: selected.id, input: text },
        {
          onDelta: (chunk) => {
            setTurns((prev) =>
              prev.map((t) => (t.id === assistantId ? { ...t, text: t.text + chunk } : t)),
            );
          },
          onEvent: (event, payload) => {
            if (event === 'usage') {
              setTurns((prev) =>
                prev.map((t) =>
                  t.id === assistantId
                    ? {
                        ...t,
                        cost: typeof payload.cost_usd === 'number' ? payload.cost_usd : undefined,
                        upstreamModel:
                          typeof payload.upstream_model === 'string'
                            ? payload.upstream_model
                            : undefined,
                      }
                    : t,
                ),
              );
            }
            if (event === 'run.failed') {
              const code = typeof payload.error_code === 'string' ? payload.error_code : '';
              setError(
                code
                  ? (ERROR_HINTS[code] ?? `运行失败：${String(payload.message ?? '')}`)
                  : '运行失败',
              );
            }
          },
          onError: (err) => setError(err.friendly),
          onDone: () => {
            setTurns((prev) =>
              prev.map((t) => (t.id === assistantId ? { ...t, streaming: false } : t)),
            );
            setConnState('done');
          },
        },
        controller.signal,
      );
    } catch (err) {
      if (controller.signal.aborted) {
        setConnState('lost');
        setError('已停止本次运行。');
      } else {
        setError(err instanceof ApiError ? err.friendly : '网络异常，请检查连接后重试。');
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
      setTurns((prev) => prev.map((t) => (t.streaming ? { ...t, streaming: false } : t)));
    }
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-57px)] max-w-4xl flex-col">
      {/* 模型选择。中转条目必须显式标注，并提示数据经第三方转发（design.md 2.2 ③⑦） */}
      <div className="border-b px-4 py-3">
        <label className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-gray-600">模型</span>
          <select
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
            className="rounded border px-2 py-1 text-sm"
            disabled={running}
          >
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.provider_label || m.id} · {m.model}
                {m.is_relay ? '（中转）' : ''}
              </option>
            ))}
          </select>
          {selected?.capabilities.length ? (
            <span className="text-xs text-gray-400">
              能力：{selected.capabilities.join('、')}
            </span>
          ) : null}
        </label>
        {selected?.is_relay ? (
          <p className="mt-2 rounded bg-amber-50 px-3 py-2 text-xs text-amber-800">
            此模型经中转提供服务，数据会经第三方转发，且实际能力可能与官方不同。
          </p>
        ) : null}
      </div>

      {/* 消息区 */}
      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {turns.length === 0 ? (
          <div className="mt-16 text-center text-sm text-gray-400">
            <p>还没有对话。</p>
            <p className="mt-1">选一个模型，发一句话试试 —— P0 阶段 mock 模型即可验证流式输出。</p>
          </div>
        ) : null}

        {turns.map((turn) => (
          <div key={turn.id} className={turn.role === 'user' ? 'text-right' : ''}>
            <div
              className={
                turn.role === 'user'
                  ? 'inline-block max-w-[80%] rounded-lg bg-gray-900 px-3 py-2 text-left text-sm text-white'
                  : 'inline-block max-w-[85%] whitespace-pre-wrap rounded-lg border px-3 py-2 text-sm'
              }
            >
              {turn.text}
              {turn.streaming ? (
                <span className="ml-0.5 inline-block h-4 w-1 animate-pulse bg-gray-400 align-text-bottom" />
              ) : null}
            </div>
            {turn.role === 'assistant' && (turn.cost !== undefined || turn.upstreamModel) ? (
              <div className="mt-1 text-xs text-gray-400">
                {turn.upstreamModel ? `上游模型 ${turn.upstreamModel}` : null}
                {turn.cost !== undefined ? ` · 本次费用 $${turn.cost.toFixed(6)}` : null}
              </div>
            ) : null}
          </div>
        ))}
      </div>

      {/* 错误与连接状态 */}
      {error ? (
        <p role="alert" className="mx-4 mb-2 rounded bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      ) : null}
      {connState === 'lost' ? (
        <p className="mx-4 mb-2 rounded bg-amber-50 px-3 py-2 text-xs text-amber-800">
          连接已中断。P1 起支持按运行编号续传（契约 GET /runs/&#123;id&#125;/events?after=序号）。
        </p>
      ) : null}

      {/* 输入区 */}
      <div className="border-t px-4 py-3">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                void onSend();
              }
            }}
            rows={2}
            placeholder="输入消息，Enter 发送，Shift+Enter 换行"
            className="flex-1 resize-none rounded border px-3 py-2 text-sm"
            disabled={running || !selected}
          />
          <button
            onClick={() => void onSend()}
            disabled={running || !selected || !input.trim()}
            className="rounded bg-gray-900 px-4 text-sm text-white disabled:opacity-40"
          >
            {running ? '生成中…' : '发送'}
          </button>
        </div>
      </div>
    </div>
  );
}

/** 运行失败时的人话提示。与契约的封闭错误码集合一一对应。 */
const ERROR_HINTS: Record<string, string> = {
  model_unavailable: '模型暂时不可用。若该条目经中转提供服务，可能是上游故障。',
  budget_exceeded: '已超出预算上限，本次运行已停止。',
  rate_limited: '请求过于频繁，请稍后再试。',
  run_conflict: '这次运行已经结束了。',
  tool_denied: '工具调用被拒绝，未执行。',
  internal_error: '服务器内部错误，请稍后重试。',
};
