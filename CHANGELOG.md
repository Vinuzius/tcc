# Histórico de versões

## Schema v1 (Arani) — 2026-11-24
- Origem: branch feat/arani-engine (merge na develop).
- Mudanças: schema `arani` com regulação, perfil, conjuntos de colunas, classificações, algoritmos com `guarantee`, regras de perfil e auditoria; trigger de conformidade em `profile_rule`; fonte separada com papel somente leitura.
- Motivo: aplicar as regras de privacidade do perfil no resultado das consultas.

## Schema v0 — 2026-11-16
- Origem: commit "feat: schema v0" (feat/auth).
- Mudanças: tabelas `perfil` e `usuario` no schema `public`, com fallback SQLite.