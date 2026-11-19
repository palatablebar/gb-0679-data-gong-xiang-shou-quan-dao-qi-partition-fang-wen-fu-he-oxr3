import hashlib,json
from decimal import Decimal
from app.errors import DomainError
from app.reasons import sources
def evaluate(rows,context):
    context=context or {}
    stages=[v for v in context.values() if isinstance(v,dict) and "metrics" in v]
    balances=[s["metrics"]["balanced"] for s in stages if "balanced" in s["metrics"]]
    if balances and not all(balances): raise DomainError("UNBALANCED","来源行未对平，不能归档")
    # 用途准入结论是封存前提：超出获准范围的访问不得封存，但不得连累已获准数据。
    conclusion=context.get("purposes")
    sealable=[];excluded=[]
    for row in rows:
        if row.get("sealable",True) and not row.get("purpose_out_of_scope"): sealable.append(row)
        else: excluded.append({**row,"reason":"PURPOSE_OUT_OF_SCOPE","detail":"实际用途超出获准范围，不能封存"})
    if rows and not sealable: raise DomainError("PURPOSE_OUT_OF_SCOPE","整批用途均未获准，不能封存")
    ids=[str(r.get("event_id",r.get("_line",""))) for r in sealable]
    if len(ids)!=len(set(ids)): raise DomainError("ARCHIVE_DUPLICATE","归档业务键重复")
    encoded=json.dumps(sealable,ensure_ascii=False,sort_keys=True,default=str).encode()
    return {"rows":sealable,"quarantine":excluded,
            "metrics":{"records":len(sealable),"source_lines":len(set(x for row in sealable for x in sources(row))),"sha256":hashlib.sha256(encoded).hexdigest(),"ready":True,
            "differences":sum(r.get("status")=="差异" for r in sealable),"purpose_out_of_scope":len(excluded),
            "purpose_verdict":(conclusion or {}).get("verdict","unknown"),"purpose_checksum":(conclusion or {}).get("checksum","")}}
