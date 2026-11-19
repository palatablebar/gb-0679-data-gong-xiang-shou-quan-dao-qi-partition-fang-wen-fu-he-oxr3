from app import purposes
from app.reasons import reject
RESOURCES={"订单":"orders","orders":"orders","客户":"customers","customers":"customers"}
def evaluate(rows,context):
    context=context or {}
    approvals=purposes.approvals_from(context)
    conclusion=context.get("purposes") or purposes.build_conclusion(rows,approvals)
    good=[];bad=[]
    for row in rows:
        resource=RESOURCES.get(row.get("resource"))
        if not resource:bad.append(reject(row,"UNKNOWN_RESOURCE","资源未登记"));continue
        part=row.get("partition","")
        if len(part)!=7 or part[4]!="-" or not part[:4].isdigit() or not part[5:].isdigit() or not 1<=int(part[5:])<=12:bad.append(reject(row,"BAD_PARTITION","分区必须为YYYY-MM"));continue
        if not row.get("principal"):bad.append(reject(row,"EMPTY_PRINCIPAL","访问主体为空"));continue
        good.append(purposes.attach({**row,"resource":resource,"partition":part},conclusion,approvals))
    return {"rows":good,"quarantine":bad,"metrics":{"accepted":len(good),"resources":len(set(r["resource"] for r in good)),
            "purpose_allowed":sum(r.get("purpose_admitted") is True for r in good),"purpose_denied":sum(r.get("purpose_out_of_scope") is True for r in good)}}
