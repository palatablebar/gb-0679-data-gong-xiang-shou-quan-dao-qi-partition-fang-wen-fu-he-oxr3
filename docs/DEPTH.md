# 深度登记 数据共享授权到期与分区访问复核

规模：中型。使用者：企业数据共享审计专员。核心规则：拒绝规则优先于允许，授权必须同时命中资源、分区和生效窗；显式拒绝不得被宽授权覆盖。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 访问采信 | 查看并运行访问采信 | `/api/accesses` | `app/modules/m1_accesses/rules.py` | `tests/test_m1.py` |
| M2 资源映射 | 查看并运行资源映射 | `/api/resources` | `app/modules/m2_resources/rules.py` | `tests/test_m2.py` |
| M3 授权定版 | 查看并运行授权定版 | `/api/grants` | `app/modules/m3_grants/rules.py` | `tests/test_m3.py` |
| M4 冲突裁决 | 查看并运行冲突裁决 | `/api/conflicts` | `app/modules/m4_conflicts/rules.py` | `tests/test_m4.py` |
| M5 分区判定 | 查看并运行分区判定 | `/api/partitions` | `app/modules/m5_partitions/rules.py` | `tests/test_m5.py` |
| M6 访问对账 | 查看并运行访问对账 | `/api/audit` | `app/modules/m6_audit/rules.py` | `tests/test_m6.py` |
| M7 审计归档 | 查看并运行审计归档 | `/api/seals` | `app/modules/m7_seals/rules.py` | `tests/test_m7.py` |
| 用途准入 | 形成并切换批次用途结论 | `/api/runs/<id>/purposes` | `app/purposes.py` | `tests/test_purposes.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-01 | 旧编码 | 默认解码失败 | 回退GB18030 | `app/modules/m1_accesses/rules.py` | `tests/test_m1.py::test_legacy_encoding_real_sample` |
| TRAP-02 | BOM | 首列名多字符 | utf-8-sig | `app/modules/m1_accesses/rules.py` | `tests/test_m1.py::test_bom_real_sample` |
| TRAP-03 | 带引号换行 | 拆成两条 | csv逻辑行 | `app/modules/m1_accesses/rules.py` | `tests/test_m1.py::test_quoted_newline_is_one_record` |
| TRAP-05 | 列数不匹配 | 静默错列 | 隔离原行 | `app/modules/m1_accesses/rules.py` | `tests/test_m1.py::test_bad_columns_real_sample` |
| TRAP-08 | 前导零ID | 编码变形 | 全程字符串 | `app/modules/m1_accesses/rules.py` | `tests/test_m1.py::test_identifier_preserved_real_sample` |
| TRAP-14 | 重复键冲突 | 后写覆盖 | 保留首条并隔离冲突行 | `app/modules/m1_accesses/rules.py` | `tests/test_m1.py::test_duplicate_conflict_real_sample` |
| TRAP-18 | 空态三态 | 一律成功 | 分别错误码 | `app/modules/m1_accesses/rules.py` | `tests/test_m1.py::test_three_empty_states` |
| TRAP-26 | 旧版本提交 | 覆盖新结果 | 版本条件更新 | `app/store.py` | `tests/test_e2e.py::test_stale_review_409` |
| TRAP-07 | 上游结果空值 | 误报拒绝 | 隔离缺失 | `app/values.py` | `tests/test_m3.py::test_real_missing_decision_not_zero` |
| TRAP-19 | 允许与拒绝重叠 | 后写覆盖 | 拒绝优先且排序证据 | `app/modules/m4_conflicts/rules.py` | `tests/test_m4.py::test_deny_priority_counterexample` |
| TRAP-23 | 授权到期点 | 多放行一次 | 半开生效窗 | `app/modules/m3_grants/rules.py` | `tests/test_m3.py::test_expiry_endpoint_excluded` |
| TRAP-27 | 混合用途批 | 整批一个结论 | 唯一结论内逐用途准入 | `app/purposes.py` | `tests/test_purposes.py::test_one_conclusion_per_batch_from_actual_purposes` |
| TRAP-28 | 拒绝用途 | 宽授权覆盖拒绝 | 用途结论抑制授权候选 | `app/modules/m3_grants/rules.py` | `tests/test_purposes.py::test_denied_purpose_suppresses_grant_hits` |
| TRAP-29 | 实际用途超范围 | 按授权结果算一致 | 判越权访问且不封存 | `app/modules/m5_partitions/rules.py` | `tests/test_purposes.py::test_out_of_scope_is_violation_even_if_consistent` |
| TRAP-30 | 同批重跑 | 重复生成结论 | 复用既有结论版本 | `app/store.py` | `tests/test_purposes.py::test_rerun_does_not_duplicate_conclusion` |
| TRAP-31 | 结论切换失败 | 覆盖旧版与依据 | 版本条件切换+回滚保留 | `app/store.py` | `tests/test_purposes.py::test_switch_failure_preserves_active_conclusion` |

## 用途准入

每批访问在采信后立即形成**唯一一份**用途准入结论（`app/purposes.py`）：结论记录批内出现的每个实际用途及其准入结果，批级`verdict`分为 `allow`（全部获准）、`partial`（部分获准）、`deny`（全部拒绝）、`not_applicable`（未声明用途）。选择逐用途准入而非整批准入：分析已获准、营销被明确拒绝的混合批若整批放行会放出拒绝用途，若整批拒绝会误拦已获准数据。

结论一经形成即为该批唯一依据：授权定版阶段，被拒用途不生成授权候选（TRAP-28）；冲突裁决阶段，被拒用途强制为`deny`，不被任何授权命中翻案（TRAP-19 叠加）；分区判定阶段，实际用途超出获准范围一律判`越权访问`并标记`sealable=False`，无论其授权效果是否“一致”（TRAP-29）；归档阶段仅封存`sealable`记录，拒绝用途单独列入隔离，不连累已获准数据；全批超范围则拒绝封存。

同批重跑（同`run_id`）只复用既有结论，不再生成新版本（TRAP-30）。结论切换需提供`version`并以版本条件更新，切换时整批重算并原子落盘；版本失效返回409，失败回滚后旧版与按来源行保存的原始用途依据均保留（TRAP-31）。原始用途值（`purpose_raw`）与标准化的`purpose`分开保存，切换不改写。用途惯例：分析=allow、营销=deny，未登记用途默认拒绝；可通过参数`purpose_approvals`或`POST /api/runs/<id>/purposes/switch`变更。

## 对账规则

输入原始逻辑行=最终采纳来源行+隔离来源行+重复行+空白行+分段表头。派生记录用_sources保存完整来源，因此分组不丢行。业务预期合计与上游申报合计之差等于逐行差异之和。结果按输入摘要、规则版本及参数产生唯一批次，事务写入；同源重跑只复用已有批次。

## 已知不覆盖

4MB以上文件需预先按业务键分批；不模拟生产支付与外部回调。人工复核只变更批次状态，不改写原始记录。
