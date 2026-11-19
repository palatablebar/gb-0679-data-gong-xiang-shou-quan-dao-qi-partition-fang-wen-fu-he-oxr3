def decide(candidates,partition):
    hits=sorted((g for g in candidates if g["from_partition"]<=partition<g["to_partition"]),key=lambda g:g["id"])
    denied=[g["id"] for g in hits if g["effect"]=="deny"]
    allowed=[g["id"] for g in hits if g["effect"]=="allow"]
    return {"effect":"deny" if denied or not allowed else "allow","matched_rules":[g["id"] for g in hits],"deny_rules":denied,"allow_rules":allowed,"conflict":bool(denied and allowed)}
def evaluate(rows,context):
    out=[]
    for row in rows:
        decision=decide(row.get("candidates",[]),row["partition"])
        # 用途结论优先：超出获准范围的用途一律拒绝，不得被授权命中翻案。
        if row.get("purpose_out_of_scope"):
            decision={**decision,"effect":"deny","purpose_block":True,
                      "rule_evidence":(" / ".join(decision["matched_rules"])+" / PURPOSE_DENY") if decision["matched_rules"] else "PURPOSE_DENY"}
        else:
            decision={**decision,"purpose_block":False,"rule_evidence":" / ".join(decision["matched_rules"]) or "NO_GRANT"}
        out.append({**row,**decision})
    return {"rows":out,"quarantine":[],"metrics":{"conflicts":sum(r["conflict"] for r in out),"explicit_denies":sum(bool(r["deny_rules"]) for r in out),"default_denies":sum(not r["matched_rules"] for r in out),"purpose_blocks":sum(r["purpose_block"] for r in out)}}
