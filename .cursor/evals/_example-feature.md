# Capability Eval 示例

> 复制为 `.cursor/evals/<your-feature>.md` 并按功能填写

## [CAPABILITY EVAL: your-feature-name]

**Task**: （一句话）

**Scope**: 对照 `scope-check` — IN SCOPE / OUT OF SCOPE

### Success Criteria

- [ ] `scope-check` 通过
- [ ] `docs/design/03-API设计.md` 已更新（若改 API）
- [ ] `docs/design/02-数据模型.md` 已更新（若改实体）
- [ ] `.\mvnw.cmd test`（或 `mvn test`）→ PASS
- [ ] `cd frontend && npm run build` → PASS
- [ ] 若改 backend：重启 + 冒烟 → PASS
- [ ] reviewers 无 BLOCKER（建议）

### Regression

- [ ] （按项目填写）
- [ ] （按项目填写）

### Grader Commands

```powershell
cd frontend && npm run build
.\mvnw.cmd test
# 冒烟：见 docs/product/dev-accounts.md（若存在）
```

### Expected Output

（用户可见结果）

### EVAL REPORT

```
Capability: _/_ 
Regression: _/_ 
Status: NOT STARTED
```
