#!/usr/bin/env python3
"""生成 docs/evidence/sage-vs-minicpm-2026-11-16 的 summary.json / summary.md。

口径对齐 docs/evidence/minicpm-local-r3-2026-11-16/summary.json 的字段结构。
"""
import gzip
import json
import os
import statistics

SRC = os.path.expanduser("~/Developer/SMAB/runs/sage-vs-minicpm-20261116")
BATCH = "sage-vs-minicpm-2026-11-16"
OUT = os.path.expanduser(f"~/Developer/SMAB/docs/evidence/{BATCH}")
DIMS = ["arguments", "planning", "recovery", "relevance", "selection", "state_tracking", "stopping"]

CELLS = [
    ("Sage-A1.5-Q4_K_M (thinking on)", "sage-think"),
    ("Sage-A1.5-Q4_K_M (thinking off)", "sage-a15-nothink"),
    ("MiniCPM-V-4.7-35B-A3B-Q4_K_M", "minicpm"),
]
FILES = {
    ("sage-think", "core", "native"): "sage-a15-q4km-think-core-native-r3",
    ("sage-think", "core", "json"): "sage-a15-q4km-think-core-json-r3",
    ("sage-think", "extra", "native"): "sage-a15-q4km-think-extra-native-r3",
    ("sage-think", "extra", "json"): "sage-a15-q4km-think-extra-json-r3",
    ("sage-a15-nothink", "core", "native"): "sage-a15-q4km-nothink-core-native-r3",
    ("sage-a15-nothink", "core", "json"): "sage-a15-q4km-nothink-core-json-r3",
    ("sage-a15-nothink", "extra", "native"): "sage-a15-q4km-nothink-extra-native-r3",
    ("sage-a15-nothink", "extra", "json"): "sage-a15-q4km-nothink-extra-json-r3",
    ("minicpm", "core", "native"): "minicpm-v47-35b-a3b-q4km-core-native-r3",
    ("minicpm", "core", "json"): "minicpm-v47-35b-a3b-q4km-core-json-r3",
    ("minicpm", "extra", "native"): "minicpm-v47-35b-a3b-q4km-extra-native-r3",
    ("minicpm", "extra", "json"): "minicpm-v47-35b-a3b-q4km-extra-json-r3",
}
SENS = {
    ("sage-think", "core", "native-512"): "sage-a15-q4km-think-core-native-maxtok512-r1",
    ("sage-think", "core", "native-2048"): "sage-a15-q4km-think-core-native-maxtok2048-r1",
}


def load(name):
    with gzip.open(os.path.join(OUT, "runs", name + ".json.gz"), "rt") as fh:
        return json.load(fh)


def runs(d):
    return d["runs"] if "runs" in d else [d]


def mean_pct(vals):
    return round(100 * sum(vals) / len(vals), 1) if vals else None


def sub_mean(rs, key, sub):
    vals = [r["summary"].get(key, {}).get(sub) for r in rs]
    vals = [v for v in vals if v is not None]
    return mean_pct(vals)


def cell_block(d):
    R = runs(d)
    overalls = [r["summary"].get("overall_mean", r["summary"].get("overall")) for r in R]
    perfects = [r["summary"].get("perfect_case_rate_mean",
                                 r["summary"].get("case_success_rate")) for r in R]
    pk = d["summary"].get("pass_at_k")
    if pk is None:
        pk = {"1": perfects[0], "2": perfects[0], "3": perfects[0]}
    comp = pt = ms = turns = cases = 0
    for r in R:
        for c in r["results"]:
            u = c.get("usage") or {}
            comp += u.get("completion_tokens") or 0
            pt += u.get("prompt_tokens") or 0
            ms += c.get("elapsed_ms") or 0
            turns += max(len(c.get("raw_turns") or [1]), 1)
            cases += 1
    secs = ms / 1000
    return {
        "overall_mean_pct": mean_pct(overalls),
        "overall_stddev_pct": round(100 * statistics.pstdev(overalls), 1) if len(overalls) > 1 else 0.0,
        "perfect_case_rate_mean_pct": mean_pct(perfects),
        "pass_at_k": {str(k): round(100 * v, 1) for k, v in pk.items()},
        "repeats": [round(100 * v, 1) for v in overalls],
        "by_dimension_pct": {k: sub_mean(R, "by_dimension", k) for k in DIMS},
        "by_split_pct": {k: sub_mean(R, "by_split", k) for k in ("core", "ood")},
        "by_horizon_pct": {k: sub_mean(R, "by_horizon", k) for k in ("0", "1", "2", "3+")},
        "throughput": {
            "avg_prompt_tokens": round(pt / cases),
            "avg_completion_tokens": round(comp / cases),
            "avg_turn_latency_s": round(secs / turns, 2),
            "approx_tok_per_s": round(comp / secs, 1),
        },
        "cases_per_repeat": cases // len(R),
    }


models = {}
rows = []
for label, tag in CELLS:
    models[label] = {}
    for ds in ("core", "extra"):
        for fmt in ("native", "json"):
            d = load(FILES[(tag, ds, fmt)])
            key = f"{ds}-{fmt}"
            models[label][key] = cell_block(d)
            rows.append((label, ds, fmt, models[label][key]))

models[CELLS[0][0]]["sensitivity"] = {
    "core-native-max_tokens-512": cell_block(load(SENS[("sage-think", "core", "native-512")])),
    "core-native-max_tokens-2048": cell_block(load(SENS[("sage-think", "core", "native-2048")])),
}

summary = {
    "batch": BATCH,
    "protocol": "temp=0, seed=0, repeats=3, schema_variant=original, ctx=16384, "
                "llama.cpp 1.0.0 (-ngl 999 -fa on --jinja), text-only, SMAB main@df492b0 datasets",
    "models": models,
}
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "summary.json"), "w") as fh:
    json.dump(summary, fh, ensure_ascii=False, indent=2)
    fh.write("\n")

lines = [f"# 书生-A1.5 vs MiniCPM-V 4.7 35B-A3B 批次 summary（2026-11-16）", "",
         "| 模型 | 数据集 | 通道 | overall 均值±σ | perfect(pass^1) | 单遍分数 |", "|---|---|---|---|---|---|"]
for label, ds, fmt, b in rows:
    lines.append("| {} | {} | {} | **{}% ± {}** | {}% | {} |".format(
        label, ds, fmt, b["overall_mean_pct"], b["overall_stddev_pct"],
        b["perfect_case_rate_mean_pct"], " / ".join(f"{v}%" for v in b["repeats"])))
lines += ["", "## 敏感性（Sage 原生形态，core × native，单遍）", "",
          "| max_tokens | overall | perfect | avg_completion | tok/s |", "|---|---:|---:|---:|---:|"]
for k, b in models[CELLS[0][0]]["sensitivity"].items():
    lines.append("| {} | {}% | {}% | {} | {} |".format(
        k.split("-")[-1], b["overall_mean_pct"], b["perfect_case_rate_mean_pct"],
        b["throughput"]["avg_completion_tokens"], b["throughput"]["approx_tok_per_s"]))
with open(os.path.join(OUT, "summary.md"), "w") as fh:
    fh.write("\n".join(lines) + "\n")
print("written:", "summary.json", "summary.md")
for label, ds, fmt, b in rows:
    print(f"{label:<34} {ds}-{fmt:<7} {b['overall_mean_pct']:5.1f} ±{b['overall_stddev_pct']:4.1f} "
          f"perfect {b['perfect_case_rate_mean_pct']:5.1f} tok/s {b['throughput']['approx_tok_per_s']:6.1f}")
