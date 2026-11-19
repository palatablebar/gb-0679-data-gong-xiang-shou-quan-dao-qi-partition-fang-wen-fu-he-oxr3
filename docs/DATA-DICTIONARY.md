# 授权定义

资源orders与订单等价，customers与客户等价。principal为主体文本，不支持模糊主体。partition为YYYY-MM；分区授权[start,end)不含end月。授权时间也为[start,end)，到期时刻立即失效。

每条授权包含主体、资源、生效窗、分区窗和allow/deny。全部条件必须同时匹配。拒绝优先，多个允许不能覆盖任何显式拒绝；无匹配默认拒绝。匹配规则ID按字典序稳定排序，冲突显示全部允许与拒绝证据。

observed为真实访问执行结果allowed或blocked；reported为上游0/1判定，留作证据。expected为实际授权复算，分区模块重建reported为执行结果便于二值对账。越权放行和误拦截分别计数，禁止用相互抵消的总数代替逐条核查。

purpose（或`用途`）为可选末列，记录每条访问的实际用途，如`分析`、`营销`，亦可写`analysis`/`marketing`。用途经规范化后进入批次用途结论：分析默认获准，营销默认明确拒绝，未登记用途默认拒绝。原始用途值保留在`purpose_raw`，不因子结论切换而改写。header含purpose时列数相应加一。

业务ID和超大整数按文本保形；Decimal参与数量金额计算，对外序列化为字符串。哨兵集合定义在app/values.py，缺失值不能当零。所有时间带UTC偏移，先转UTC比较，业务日按指定地区划分。区间统一[start,end)。重复业务键保留第一条、完全相同行计重复；值冲突行隔离且保留原值。空文件、全空白、仅表头分开拒绝。

运行清单包括输入sha256、规则版本、参数、生成时刻与耗时。源行编号以CSV解析器的物理结束行号表示，引号内换行不增加记录数。输入超过4MB返回413，非法表头和类型返回422，失效版本复核返回409。

## 用途结论

`GET /api/runs/<id>/purposes`返回`conclusion`（唯一结论：`entries`逐用途effect、`approved`、`denied`、`verdict`、`checksum`、`version`）、`active_version`、`history`（保留的历史版本）与`basis`（按来源行保存的原始用途依据）。`POST /api/runs/<id>/purposes/switch`接收`version`与`approvals`对象，版本失效返回409；切换失败不改变活动结论，旧版与原始依据保留。同批重跑不生成新结论版本。