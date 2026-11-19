# 接口

模块GET使用仓内样例，模块POST可传csv或rows与context，直接计算当前规则。/api/runs使用完整流水线并原子保存。每个阶段返回rows、quarantine、metrics；后续阶段还返回累计隔离。/api/upload接收multipart文件file。/api/runs/<id>/archive只导出一份带清单与证据的CSV。

`GET /api/runs/<id>/purposes`返回该批唯一用途准入结论、历史版本与原始用途依据。`POST /api/runs/<id>/purposes/switch`以`version`做条件切换，返回新结论或409。
