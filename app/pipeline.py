import time
from app.config import ROOT,MODULES
from app.errors import DomainError
from app.values import scalar
from app.manifest import digest,manifest
from app import store,purposes
from app.modules.m1_accesses.rules import evaluate as stage1
from app.modules.m2_resources.rules import evaluate as stage2
from app.modules.m3_grants.rules import evaluate as stage3
from app.modules.m4_conflicts.rules import evaluate as stage4
from app.modules.m5_partitions.rules import evaluate as stage5
from app.modules.m6_audit.rules import evaluate as stage6
from app.modules.m7_seals.rules import evaluate as stage7
STAGES=[stage1,stage2,stage3,stage4,stage5,stage6,stage7]
def load_sample(name):
    if name not in {"dirty.csv","clean.csv","legacy.csv","mixed.csv"}: raise DomainError("BAD_SAMPLE","样例不存在",404)
    return (ROOT/"sample_data"/name).read_bytes()
def calculate(raw,params=None,stop=6):
    params=params or {};started=time.monotonic();context={"parameters":params,"raw":raw,"quarantine":[]};stages=[];rows=[];conclusion=None
    for index,stage in enumerate(STAGES[:stop+1]):
        if index==1:
            # 采信后立即定版：每批只形成一份用途准入结论，后续阶段共同服从。
            conclusion=purposes.build_conclusion(rows,purposes.approvals_from(context))
            context["purposes"]=conclusion
        result=stage(raw if index==0 else rows,context)
        result=scalar(result);rows=result["rows"]
        context["quarantine"].extend(result.get("quarantine",[]))
        if index==0: context["intake"]=result["metrics"]
        result["cumulative_quarantine"]=list(context["quarantine"])
        context[MODULES[index][0]]=result
        stages.append(result)
    out={"run_id":digest(raw,params)[:20],"stages":stages,"manifest":manifest(raw,params,started),"parameters":params}
    if conclusion is not None: out["purposes"]=conclusion
    return out
def execute(raw,params=None):
    result=calculate(raw,params)
    saved=store.save(result["run_id"],result,raw)
    # 同一批次重跑复用既有结论；为新结论切换失败时保留旧版与原始用途依据。
    conclusion=store.ensure_conclusion(result["run_id"],result.get("purposes"),result["stages"][0]["rows"])
    saved["purposes"]=conclusion
    return saved
def stage_preview(index,payload):
    if "rows" in payload and index>0:
        if not isinstance(payload["rows"],list) or any(not isinstance(row,dict) for row in payload["rows"]): raise DomainError("BAD_ROWS","记录需要对象列表")
        if not isinstance(payload.get("context",{}),dict): raise DomainError("BAD_CONTEXT","上下文需要对象")
        return scalar(STAGES[index](payload["rows"],payload.get("context",{"parameters":{},"quarantine":[]})))
    raw=payload.get("csv")
    raw=raw.encode() if isinstance(raw,str) else load_sample(payload.get("sample","dirty.csv"))
    return calculate(raw,payload.get("parameters",{}),index)["stages"][-1]
