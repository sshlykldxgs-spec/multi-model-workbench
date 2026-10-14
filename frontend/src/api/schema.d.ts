/**
 * ⚠️ 占位文件 —— 真实内容由 OpenAPI 自动生成，请勿手改。
 *
 * 生成方式（frontend/AGENTS.md 第 2 节：类型必须由 OpenAPI 自动生成）：
 *   后端跑起来后执行 `npm run gen:api`
 *
 * 之所以先放占位：npm install 之前 tsc 无法解析 import，
 * 会让 P0 的类型门禁形同虚设。占位只覆盖当前用到的类型，
 * 一旦后端接口变化，必须重新生成而不是在这里加字段。
 */

export interface components {
  schemas: {
    MeResponse: {
      id: string;
      email: string;
      role: 'admin' | 'member';
    };
    ModelInfo: {
      id: string;
      protocol: string;
      model: string;
      provider_label: string;
      capabilities: string[];
      is_relay: boolean;
      enabled: boolean;
    };
    ErrorResponse: {
      error: {
        code: string;
        message: string;
        request_id: string;
        detail?: Record<string, unknown>;
      };
    };
  };
}
