-- 业务数据与向量在同一个 PostgreSQL 里（A-3）。
-- pgvector 必须先建扩展，否则 vector 类型不可用。
CREATE EXTENSION IF NOT EXISTS vector;

-- 为将来的中文关键词检索预留（design.md 12.5.2 建议第一版纯向量，
-- 评测集出来后再决定是否加 pg_bigm 混合检索）。
-- 扩展镜像里未预装，所以这里注释掉，需要时再装：
-- CREATE EXTENSION IF NOT EXISTS pg_bigm;
