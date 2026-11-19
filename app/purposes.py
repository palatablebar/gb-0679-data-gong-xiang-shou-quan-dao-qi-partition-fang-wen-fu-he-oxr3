"""用途准入：为每批访问形成唯一的用途结论，并逐条服从该结论。"""
import hashlib,json,unicodedata
from datetime import datetime,timezone
from app.config import RULE_VERSION
from app.errors import DomainError

ALLOW={"allow","allowed","approve","approved","permit","permitted","1","true","是","准予","获准"}
DENY={"deny","denied","reject","rejected","0","false","否","拒绝","明确拒绝","驳回"}
MISSING={"","-","n/a","null","none"}
ALIASES={"分析":"分析","analysis":"分析","analyze":"分析","analytics":"分析","分析用途":"分析",
         "营销":"营销","marketing":"营销","market":"营销","市场营销":"营销","营销用途":"营销"}
# 场景基线：分析用途已获准，营销用途被明确拒绝；未登记用途按默认拒绝处理。
DEFAULT_APPROVALS={"分析":"allow","营销":"deny"}
PARAM_KEYS=("purpose_approvals","purpose_grants","purposes")

def normalize_purpose(value):
    if value is None: return None
    text=unicodedata.normalize("NFKC",str(value)).strip()
    if text.lower() in MISSING: return None
    return ALIASES.get(text.lower(),text)

def _effect(value):
    if isinstance(value,bool): return "allow" if value else "deny"
    text=unicodedata.normalize("NFKC",str(value)).strip().lower()
    if text in ALLOW: return "allow"
    if text in DENY: return "deny"
    raise DomainError("BAD_PURPOSE_APPROVAL","用途准入结论必须为allow或deny")

def approvals_from(context):
    context=context or {};params=context.get("parameters") or {}
    raw=None
    for key in PARAM_KEYS:
        if key in params: raw=params[key];break
    if raw is None and "purpose_approvals" in context: raw=context["purpose_approvals"]
    if raw is None: raw=DEFAULT_APPROVALS
    if not isinstance(raw,dict): raise DomainError("BAD_PURPOSE_APPROVAL","用途准入结论需要对象")
    approvals={}
    for key,value in raw.items():
        purpose=normalize_purpose(key)
        if purpose is None: raise DomainError("BAD_PURPOSE_APPROVAL","用途名称不能为空")
        approvals[purpose]=_effect(value)
    return approvals

def resolve(purpose,approvals): return "allow" if approvals.get(purpose)=="allow" else "deny"

def build_conclusion(rows,approvals,run_id=None):
    """由整批实际用途形成唯一结论；同一结论内不同用途分别给出准入结果。"""
    entries=[];seen=set()
    for row in rows:
        purpose=normalize_purpose(row.get("purpose"))
        if purpose is None or purpose in seen: continue
        seen.add(purpose);effect=resolve(purpose,approvals)
        entries.append({"purpose":purpose,"effect":effect,"reason":"PURPOSE_APPROVED" if effect=="allow" else "PURPOSE_DENIED"})
    entries.sort(key=lambda item:item["purpose"])
    approved=[item["purpose"] for item in entries if item["effect"]=="allow"]
    denied=[item["purpose"] for item in entries if item["effect"]=="deny"]
    verdict="not_applicable" if not entries else "deny" if not approved else "allow" if not denied else "partial"
    digest=hashlib.sha256(json.dumps({"entries":entries,"approvals":sorted(approvals.items())},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return {"run_id":run_id,"version":1,"entries":entries,"approved":approved,"denied":denied,"out_of_scope":denied,
            "verdict":verdict,"checksum":digest,"rule_version":RULE_VERSION,
            "generated_at":datetime.now(timezone.utc).isoformat()}

def conclusion_effect(conclusion,purpose):
    for entry in (conclusion or {}).get("entries",[]):
        if entry["purpose"]==purpose: return entry["effect"]
    return None

def attach(row,conclusion=None,approvals=None):
    """把用途结论挂到访问行；原始用途值单独保留为证据。"""
    raw=row.get("purpose");purpose=normalize_purpose(raw)
    if purpose is None:
        return {**row,"purpose":raw,"purpose_raw":raw,"purpose_effect":"not_declared","purpose_admitted":None,
                "purpose_out_of_scope":False,"purpose_evidence":"NO_PURPOSE"}
    effect=conclusion_effect(conclusion,purpose)
    if effect is None: effect=resolve(purpose,approvals or {})
    return {**row,"purpose":purpose,"purpose_raw":raw,"purpose_effect":effect,"purpose_admitted":effect=="allow",
            "purpose_out_of_scope":effect=="deny","purpose_evidence":f"{purpose} -> {effect}"}
