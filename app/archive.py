import csv,io,json
def build_archive(run):
    stream=io.StringIO(newline="");writer=csv.writer(stream)
    writer.writerow(["run_id","input_sha256","rule_version","kind","source_lines","reason","purpose","purpose_effect","purpose_verdict","purpose_checksum","evidence"])
    meta=run["manifest"];conclusion=run.get("purposes") or {};verdict=conclusion.get("verdict","");checksum=conclusion.get("checksum","")
    for row in run["stages"][-1]["rows"]:
        writer.writerow([run["run_id"],meta["input_sha256"],meta["rule_version"],"accepted",json.dumps(row.get("_sources",[])),row.get("status",""),
                         row.get("purpose",""),row.get("purpose_effect",""),verdict,checksum,json.dumps(row,ensure_ascii=False)])
    for row in run["stages"][-1].get("cumulative_quarantine",[]):
        writer.writerow([run["run_id"],meta["input_sha256"],meta["rule_version"],"quarantine",json.dumps(row.get("_sources",[])),row.get("reason",""),
                         row.get("purpose",""),row.get("purpose_effect",""),verdict,checksum,json.dumps(row,ensure_ascii=False)])
    return "﻿"+stream.getvalue()
