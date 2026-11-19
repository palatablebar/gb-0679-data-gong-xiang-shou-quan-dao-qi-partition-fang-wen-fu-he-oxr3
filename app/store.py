import sqlite3,json,base64
from datetime import datetime,timezone
from app.config import DATA_DIR,RULE_VERSION
from app import purposes
from app.errors import DomainError
def connect():
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DATA_DIR/"records.db",timeout=20)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY,payload TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,decision TEXT NOT NULL DEFAULT '待复核')")
    columns={r[1] for r in db.execute("PRAGMA table_info(runs)")}
    if "raw" not in columns: db.execute("ALTER TABLE runs ADD COLUMN raw BLOB")
    # 原始用途依据：按来源行永久保留，任何结论切换都不得覆盖。
    db.execute("CREATE TABLE IF NOT EXISTS purpose_basis (run_id TEXT NOT NULL,source_line INTEGER NOT NULL,purpose_raw TEXT,purpose TEXT,PRIMARY KEY(run_id,source_line))")
    # 结论版本历史：旧版保留，供切换失败时回退。
    db.execute("CREATE TABLE IF NOT EXISTS conclusions (run_id TEXT NOT NULL,version INTEGER NOT NULL,checksum TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(run_id,version))")
    db.execute("CREATE TABLE IF NOT EXISTS conclusion_heads (run_id TEXT PRIMARY KEY,version INTEGER NOT NULL,checksum TEXT NOT NULL)")
    return db
def save(run_id,payload,raw=None):
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO runs(id,payload,raw) VALUES (?,?,?)",(run_id,json.dumps(payload,ensure_ascii=False),raw))
    return get(run_id)
def _run_row(db,run_id): return db.execute("SELECT payload,version,decision,raw FROM runs WHERE id=?",(run_id,)).fetchone()
def get(run_id):
    with connect() as db: row=_run_row(db,run_id)
    if not row: raise DomainError("NOT_FOUND","批次不存在",404)
    run={**json.loads(row[0]),"version":row[1],"decision":row[2]}
    conclusion=get_conclusion(run_id)
    if conclusion: run["purposes"]=conclusion
    return run
def latest():
    with connect() as db: row=db.execute("SELECT id FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()
    return get(row[0]) if row else None
def history():
    with connect() as db: return [{"run_id":i,"version":v,"decision":d} for i,v,d in db.execute("SELECT id,version,decision FROM runs ORDER BY rowid DESC")]
def review(run_id,version,decision):
    if decision not in {"已复核","退回复核"}: raise DomainError("BAD_DECISION","复核状态无效")
    with connect() as db:
        cursor=db.execute("UPDATE runs SET version=version+1,decision=? WHERE id=? AND version=?",(decision,run_id,version))
        if cursor.rowcount!=1:
            if not db.execute("SELECT 1 FROM runs WHERE id=?",(run_id,)).fetchone(): raise DomainError("NOT_FOUND","批次不存在",404)
            raise DomainError("STALE_VERSION","版本已更新，请刷新",409)
    return get(run_id)
def _record_basis(db,run_id,rows):
    for row in rows:
        line=row.get("_line",0)
        raw=row.get("purpose")
        db.execute("INSERT OR IGNORE INTO purpose_basis(run_id,source_line,purpose_raw,purpose) VALUES (?,?,?,?)",
                   (run_id,line,None if raw is None else str(raw),purposes.normalize_purpose(raw)))
def _basis_rows(db,run_id):
    return [{"purpose":raw} for (raw,) in db.execute("SELECT purpose_raw FROM purpose_basis WHERE run_id=? ORDER BY source_line",(run_id,))]
def _head(db,run_id): return db.execute("SELECT version,checksum FROM conclusion_heads WHERE run_id=?",(run_id,)).fetchone()
def _payload(db,run_id,version):
    row=db.execute("SELECT payload FROM conclusions WHERE run_id=? AND version=?",(run_id,version)).fetchone()
    return json.loads(row[0]) if row else None
def _store_conclusion(db,run_id,conclusion,version=None):
    version=int(version if version is not None else conclusion.get("version",1));now=datetime.now(timezone.utc).isoformat()
    conclusion={**conclusion,"run_id":run_id,"version":version,"rule_version":RULE_VERSION,"generated_at":conclusion.get("generated_at") or now}
    db.execute("INSERT OR REPLACE INTO conclusions(run_id,version,checksum,payload,created_at) VALUES (?,?,?,?,?)",
               (run_id,version,conclusion["checksum"],json.dumps(conclusion,ensure_ascii=False),now))
    db.execute("INSERT OR REPLACE INTO conclusion_heads(run_id,version,checksum) VALUES (?,?,?)",(run_id,version,conclusion["checksum"]))
    return conclusion
def _sync_payload(db,run_id,conclusion):
    row=db.execute("SELECT payload FROM runs WHERE id=?",(run_id,)).fetchone()
    if not row: return
    payload=json.loads(row[0]);payload["purposes"]=conclusion
    db.execute("UPDATE runs SET payload=? WHERE id=?",(json.dumps(payload,ensure_ascii=False),run_id))
def ensure_conclusion(run_id,proposed,rows):
    """首批生成唯一结论；同批重跑只复用既有结论，不重复生成新版本。"""
    with connect() as db:
        _record_basis(db,run_id,rows)
        head=_head(db,run_id)
        if head: return _payload(db,run_id,head[0])
        if not proposed: proposed=purposes.build_conclusion(_basis_rows(db,run_id),{})
        conclusion=_store_conclusion(db,run_id,proposed)
        _sync_payload(db,run_id,conclusion)
        return conclusion
def get_conclusion(run_id):
    with connect() as db:
        head=_head(db,run_id)
        return _payload(db,run_id,head[0]) if head else None
def purpose_report(run_id):
    with connect() as db:
        if not _run_row(db,run_id): raise DomainError("NOT_FOUND","批次不存在",404)
        head=_head(db,run_id)
        if not head: return {"run_id":run_id,"conclusion":None,"history":[],"basis":[]}
        history=[{"version":v,"checksum":c,"created_at":t,"conclusion":json.loads(p)} for v,c,t,p in db.execute("SELECT version,checksum,created_at,payload FROM conclusions WHERE run_id=? ORDER BY version",(run_id,))]
        basis=[{"source_line":l,"purpose_raw":r,"purpose":p} for l,r,p in db.execute("SELECT source_line,purpose_raw,purpose FROM purpose_basis WHERE run_id=? ORDER BY source_line",(run_id,))]
        return {"run_id":run_id,"conclusion":_payload(db,run_id,head[0]),"active_version":head[0],"history":history,"basis":basis}
def switch_conclusion(run_id,version,approvals):
    """带版本条件的结论切换：成功则整批重算并原子落盘；失败则回滚，旧版与原始用途依据保留。"""
    if not isinstance(version,int): raise DomainError("BAD_VERSION","请提供版本号")
    if not isinstance(approvals,dict): raise DomainError("BAD_PURPOSE_APPROVAL","用途准入结论需要对象")
    normalized=purposes.approvals_from({"purpose_approvals":approvals})
    row=None;raw=None
    with connect() as db:
        head=_head(db,run_id)
        run_row=_run_row(db,run_id)
        if not run_row: raise DomainError("NOT_FOUND","批次不存在",404)
        if not head: raise DomainError("STALE_VERSION","批次尚无用途结论，请重新运行",409)
        if head[0]!=version: raise DomainError("STALE_VERSION","结论版本已更新，请刷新",409)
        stored_payload=json.loads(run_row[0]);raw=run_row[3]
        old=_payload(db,run_id,head[0])
        proposed=purposes.build_conclusion(_basis_rows(db,run_id),normalized)
        if proposed["checksum"]==head[1]:
            return old
        try:
            if raw is None: raise DomainError("STALE_VERSION","缺少原始输入，无法重算，请重新运行",409)
            from app import pipeline
            params=dict(stored_payload.get("parameters") or {});params["purpose_approvals"]=normalized
            recomputed=pipeline.calculate(bytes(raw),params)
            recomputed["run_id"]=run_id;recomputed["version"]=run_row[1];recomputed["decision"]=run_row[2]
            conclusion=_store_conclusion(db,run_id,proposed,version=version+1)
            recomputed["purposes"]=conclusion
            db.execute("UPDATE runs SET payload=? WHERE id=?",(json.dumps(recomputed,ensure_ascii=False),run_id))
        except Exception:
            db.rollback();raise
    return conclusion
