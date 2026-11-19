from app.reasons import reject
from app.values import number
from app.errors import DomainError
def evaluate(rows,context):
    good=[];bad=[]
    for row in rows:
        if row.get("observed") not in {"allowed","blocked"}:bad.append(reject(row,"BAD_ACCESS_OUTCOME","访问结果必须为allowed或blocked"));continue
        effect=row["effect"];expected="1" if effect=="allow" else "0";actual="1" if row["observed"]=="allowed" else "0"
        # 实际用途超出获准范围即越权访问：即使授权效果一致也不得视为通过。
        out_of_scope=bool(row.get("purpose_out_of_scope")) or row.get("purpose_effect")=="deny"
        violation="越权访问" if out_of_scope and actual=="1" else "越权放行" if expected=="0" and actual=="1" else "误拦截" if expected=="1" and actual=="0" else "一致"
        good.append({**row,"expected":expected,"reported":actual,"upstream_decision":row["reported"],"partition_result":"授权内" if row["matched_rules"] else "未授权分区",
                     "purpose_result":"超出获准范围" if out_of_scope else "获准范围内" if row.get("purpose_effect")=="allow" else "未声明用途",
                     "violation":violation,"sealable":not out_of_scope})
    return {"rows":good,"quarantine":bad,"metrics":{"allowed":sum(r["expected"]=="1" for r in good),"blocked":sum(r["expected"]=="0" for r in good),
            "violations":sum(r["violation"] in {"越权放行","越权访问"} for r in good),"false_blocks":sum(r["violation"]=="误拦截" for r in good),
            "purpose_violations":sum(r["violation"]=="越权访问" for r in good),"out_of_scope":sum(not r["sealable"] for r in good)}}
