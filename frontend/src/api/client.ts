/**
 * API 客户端。
 *
 * 规则（frontend/AGENTS.md 第 2、9 节）：
 *   - 类型由 OpenAPI 自动生成（src/api/schema.d.ts），不手写接口类型。
 *   - 错误码是封闭集合，每个码都要有人话提示。
 *   - 会话靠 Cookie，所以每个请求都要带上凭据。
 */

import type { components } from './schema';

export type ModelInfo = components['schemas']['ModelInfo'];
export type MeResponse = components['schemas']['MeResponse'];

/** 契约第 2 节的封闭错误码集合。 */
export const ERROR_MESSAGES: Record<string, string> = {
  unauthorized: '登录状态已过期，请重新登录。',
  forbidden: '你没有权限执行这个操作。',
  not_found: '找不到请求的内容。',
  validation_failed: '提交的内容不符合要求，请检查后重试。',
  model_unavailable: '模型暂时不可用。若该条目经中转提供服务，可能是上游故障。',
  rate_limited: '操作过于频繁，请稍后再试。',
  budget_exceeded: '已超出预算上限，本次运行已停止。请联系管理员调整额度。',
  run_conflict: '这次运行已经结束了，无法再操作。',
  tool_denied: '这个工具调用被拒绝，未执行。',
  internal_error: '服务器内部错误，请稍后重试。',
};

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly requestId: string,
  ) {
    super(message);
  }
  /** 给用户看的话。未知错误码也要有兜底，不能只弹"出错了"。 */
  get friendly(): string {
    return ERROR_MESSAGES[this.code] ?? `请求失败：${this.message}`;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  });

  if (!res.ok) {
    let code = 'internal_error';
    let message = res.statusText;
    let requestId = '';
    try {
      const body = await res.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? message;
      requestId = body?.error?.request_id ?? '';
    } catch {
      /* 响应不是 JSON，用兜底文案 */
    }
    throw new ApiError(code, message, requestId);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  me: () => apiFetch<MeResponse>('/api/v1/auth/me'),
  login: (email: string, password: string) =>
    apiFetch<MeResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  logout: () => apiFetch<{ ok: boolean }>('/api/v1/auth/logout', { method: 'POST' }),
  models: () => apiFetch<{ items: ModelInfo[] }>('/api/v1/models'),
};

/**
 * 以 SSE 方式启动一次运行。
 *
 * 用 fetch + ReadableStream 而不是 EventSource，因为需要 POST 与自定义头
 * （Idempotency-Key 是契约要求的，防止重复扣费）。
 */
export interface RunHandlers {
  onDelta: (text: string) => void;
  onEvent: (event: string, payload: Record<string, unknown>) => void;
  onError: (err: ApiError) => void;
  onDone: () => void;
}

export async function startRun(
  conversationId: string,
  body: { model_id: string; input: string },
  handlers: RunHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`/api/v1/conversations/${conversationId}/runs`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      // 幂等键：同一键重复提交不会重复扣费
      'Idempotency-Key': crypto.randomUUID(),
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok) {
    let code = 'internal_error';
    let message = res.statusText;
    let requestId = '';
    try {
      const parsed = await res.json();
      code = parsed?.error?.code ?? code;
      message = parsed?.error?.message ?? message;
      requestId = parsed?.error?.request_id ?? '';
    } catch {
      /* 兜底 */
    }
    handlers.onError(new ApiError(code, message, requestId));
    return;
  }
  if (!res.body) {
    handlers.onError(new ApiError('internal_error', '响应没有内容', ''));
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  // SSE 以空行分帧；每帧里 event:/data: 各占一行。
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep = buffer.indexOf('\n\n');
    while (sep !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      handleFrame(frame, handlers);
      sep = buffer.indexOf('\n\n');
    }
  }
  handlers.onDone();
}

function handleFrame(frame: string, handlers: RunHandlers): void {
  let eventName = 'message';
  let data = '';
  for (const line of frame.split('\n')) {
    if (line.startsWith('event: ')) eventName = line.slice(7);
    else if (line.startsWith('data: ')) data += line.slice(6);
  }
  if (!data) return;

  let payload: Record<string, unknown> = {};
  try {
    const parsed = JSON.parse(data);
    payload = parsed?.payload ?? {};
    handlers.onEvent(parsed?.event ?? eventName, payload);
  } catch {
    return;
  }

  if (eventName === 'message.delta' && typeof payload.text === 'string') {
    handlers.onDelta(payload.text);
  }
}
