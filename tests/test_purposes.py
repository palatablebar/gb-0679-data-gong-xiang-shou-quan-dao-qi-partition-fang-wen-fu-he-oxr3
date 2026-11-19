import pytest
from app import purposes,store
from app.errors import DomainError
from app.pipeline import calculate,execute,load_sample

def mixed(): return load_sample("mixed.csv")

# --- 结论形成：整批准入 vs 逐条用途 ---

def test_one_conclusion_per_batch_from_actual_purposes():
    c=calculate(mixed())["purposes"]
    assert c["verdict"]=="partial"
    assert c["approved"]==["分析"] and c["denied"]==["营销"]
    assert {e["purpose"] for e in c["entries"]}=={"分析","营销"}

def test_conclusion_unique_record():
    c=calculate(mixed())["purposes"]
    assert len(c["entries"])==len({e["purpose"] for e in c["entries"]})
    assert c["checksum"] and c["rule_version"]

def test_analysis_admitted_marketing_denied():
    c=calculate(mixed())["purposes"]
    assert purposes.conclusion_effect(c,"分析")=="allow"
    assert purposes.conclusion_effect(c,"营销")=="deny"

def test_unknown_purpose_defaults_to_deny():
    assert purposes.resolve("未知用途",{"分析":"allow"})=="deny"

def test_batch_all_denied_verdict():
    c=purposes.build_conclusion([{"purpose":"营销"},{"purpose":"营销"}],{"营销":"deny"})
    assert c["verdict"]=="deny" and c["denied"]==["营销"]

def test_batch_all_allowed_verdict():
    c=purposes.build_conclusion([{"purpose":"分析"}],{"分析":"allow"})
    assert c["verdict"]=="allow" and c["approved"]==["分析"]

# --- 授权命中服从用途结论 ---

def test_denied_purpose_suppresses_grant_hits():
    r=calculate(mixed())
    marketing=[row for row in r["stages"][2]["rows"] if row["purpose"]=="营销"]
    assert marketing and all(row["candidate_count"]==0 for row in marketing)

def test_allowed_purpose_keeps_grant_hits():
    r=calculate(mixed());orders=[row for row in r["stages"][2]["rows"] if row["purpose"]=="分析" and row["principal"]=="analyst"]
    assert any(row["candidate_count"]>0 for row in orders)

def test_partition_judgement_follows_conclusion():
    r=calculate(mixed())
    marketing=[row for row in r["stages"][4]["rows"] if row["purpose"]=="营销"]
    assert all(row["effect"]=="deny" and row["partition_result"]=="未授权分区" for row in marketing)

def test_out_of_scope_is_violation_even_if_consistent():
    r=calculate(mixed())
    marketing=[row for row in r["stages"][4]["rows"] if row["purpose_out_of_scope"]]
    assert marketing and all(row["violation"]=="越权访问" and row["sealable"] is False for row in marketing)
    assert r["stages"][4]["metrics"]["purpose_violations"]==len(marketing)

# --- 封存服从用途结论 ---

def test_seal_excludes_denied_purpose_without_blocking_approved():
    r=calculate(mixed());seal=r["stages"][6]
    assert seal["metrics"]["ready"] is True
    assert all(row["purpose"]=="分析" for row in seal["rows"])
    assert len(seal["quarantine"])==r["stages"][4]["metrics"]["purpose_violations"]

def test_seal_rejects_when_all_out_of_scope():
    rows=[{"event_id":"1","_sources":[1],"purpose":"营销","purpose_out_of_scope":True,"sealable":False}]
    with pytest.raises(DomainError) as e:__import__("app.modules.m7_seals.rules",fromlist=["evaluate"]).evaluate(rows,{})
    assert e.value.code=="PURPOSE_OUT_OF_SCOPE"

# --- 幂等与版本切换 ---

def test_rerun_does_not_duplicate_conclusion():
    execute(mixed());first=store.get_conclusion(calculate(mixed())["run_id"])
    second=execute(mixed())
    assert second["purposes"]["checksum"]==first["checksum"] and second["purposes"]["version"]==first["version"]
    assert len(store.purpose_report(second["run_id"])["history"])==1

def test_switch_keeps_history_and_basis():
    run=execute(mixed());rid=run["run_id"]
    switched=store.switch_conclusion(rid,run["purposes"]["version"],{"分析":"allow","营销":"allow"})
    report=store.purpose_report(rid)
    assert switched["version"]==run["purposes"]["version"]+1
    assert switched["verdict"]=="allow"
    assert len(report["history"])==2
    assert {b["purpose"] for b in report["basis"]}=={"分析","营销"}

def test_stale_switch_rejected_and_old_version_preserved():
    run=execute(mixed());rid=run["run_id"];old=run["purposes"]["version"]
    store.switch_conclusion(rid,old,{"分析":"deny","营销":"allow"})
    with pytest.raises(DomainError) as e:store.switch_conclusion(rid,old,{"分析":"deny","营销":"allow"})
    assert e.value.code=="STALE_VERSION"
    report=store.purpose_report(rid)
    assert [h["version"] for h in report["history"]]==[1,2]

def test_switch_failure_preserves_active_conclusion():
    run=execute(mixed());rid=run["run_id"];before=store.purpose_report(rid)
    with pytest.raises(DomainError):store.switch_conclusion(rid,999,{"分析":"allow"})
    after=store.purpose_report(rid)
    assert after["active_version"]==before["active_version"]
    assert after["conclusion"]["checksum"]==before["conclusion"]["checksum"]
    assert after["basis"]==before["basis"]

def test_switch_updates_downstream_results():
    run=execute(mixed());rid=run["run_id"]
    switched=store.switch_conclusion(rid,run["purposes"]["version"],{"分析":"allow","营销":"allow"})
    reloaded=store.get(rid)
    assert switched["verdict"]=="allow"
    assert reloaded["stages"][6]["metrics"]["purpose_out_of_scope"]==0
    assert all(row["purpose_effect"]=="allow" for row in reloaded["stages"][4]["rows"])

def test_purpose_api(client):
    run=execute(mixed());rid=run["run_id"]
    body=client.get(f"/api/runs/{rid}/purposes").get_json()
    assert body["conclusion"]["verdict"]=="partial" and body["basis"]
    r=client.post(f"/api/runs/{rid}/purposes/switch",json={"version":body["active_version"],"approvals":{"分析":"allow","营销":"allow"}})
    assert r.status_code==200 and r.get_json()["verdict"]=="allow"
