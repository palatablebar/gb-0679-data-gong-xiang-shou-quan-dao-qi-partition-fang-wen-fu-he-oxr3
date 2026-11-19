from flask import render_template
from app.config import MODULES,TITLE,SHORT
from app.pipeline import execute,load_sample
from app import store
def register_pages(app):
    def page(index):
        run=store.latest() or execute(load_sample("dirty.csv"))
        stage=run["stages"][index]
        rows=stage["rows"]
        columns=[['event_id', 'principal', 'resource', 'partition', 'access_time', 'observed', 'purpose', 'purpose_effect'], ['event_id', 'principal', 'resource', 'partition', 'purpose', 'purpose_effect'], ['event_id', 'principal', 'resource', 'partition', 'at', 'candidate_count', 'purpose_effect'], ['event_id', 'principal', 'partition', 'purpose', 'rule_evidence', 'effect', 'conflict'], ['event_id', 'principal', 'resource', 'partition', 'purpose', 'purpose_result', 'effect', 'observed', 'partition_result', 'violation'], ['event_id', 'principal', 'purpose', 'purpose_result', 'expected', 'reported', 'difference', 'violation', 'status'], ['event_id', 'principal', 'resource', 'partition', 'purpose', 'purpose_effect', 'rule_evidence', 'violation', 'status']][index]
        labels={'event_id': '事件号', 'principal': '主体', 'resource': '资源', 'partition': '分区', 'access_time': '访问时刻', 'observed': '执行结果', 'at': '事件 UTC', 'candidate_count': '生效授权数', 'rule_evidence': '命中规则', 'effect': '授权裁决', 'conflict': '规则冲突', 'partition_result': '分区裁决', 'violation': '执行差异', 'expected': '应允许', 'reported': '实允许', 'difference': '差异', 'status': '结论', 'resources': '资源数', 'accepted': '采纳行', 'active_hits': '生效命中', 'grant_versions': '授权数', 'conflicts': '冲突行', 'explicit_denies': '显式拒绝', 'default_denies': '默认拒绝', 'allowed': '应放行', 'blocked': '应拒绝', 'violations': '越权放行', 'false_blocks': '误拦截', 'records': '封存数', 'source_lines': '来源行', 'sha256': '摘要', 'ready': '可封存', 'differences': '差异数', 'purpose': '实际用途', 'purpose_raw': '原始用途值', 'purpose_effect': '用途准入', 'purpose_result': '用途判定', 'purpose_admitted': '用途获准', 'purpose_out_of_scope': '超出获准范围', 'purpose_evidence': '用途依据', 'purpose_blocks': '用途拦截', 'purpose_suppressed': '用途抑制授权', 'purpose_violations': '越权访问', 'out_of_scope': '超范围行', 'purpose_verdict': '用途结论', 'purpose_checksum': '用途结论摘要', 'purpose_denied_records': '拒绝用途记录', 'purpose_allowed': '获准用途行', 'purpose_denied': '拒绝用途行', 'sealable': '可封存', 'purpose_out_of_scope': '超出获准范围'}
        for key,label in {'accepted_inputs': '采纳来源行', 'quarantine_inputs': '隔离来源行', 'output_records': '结果记录', 'input': '输入行', 'excluded': '排除行', 'balanced': '行数平衡', 'expected_total': '预期合计', 'reported_total': '申报合计', 'differences': '差异项', 'blank': '空行', 'repeated_headers': '分段表头', 'encoding': '编码', 'duplicate': '重复行', 'quarantine': '隔离行', 'accepted': '采纳行', 'sha256': '校验摘要', 'ready': '可归档'}.items(): labels.setdefault(key,label)
        return render_template(f"m{index+1}.html",title=TITLE,short=SHORT,modules=MODULES,index=index,run=run,stage=stage,rows=rows,columns=columns[:12],history=store.history(),labels=labels)
    app.add_url_rule("/",view_func=lambda:page(4))
    for index,(slug,name) in enumerate(MODULES):
        app.add_url_rule("/"+slug,endpoint="page_"+slug,view_func=lambda index=index:page(index))
