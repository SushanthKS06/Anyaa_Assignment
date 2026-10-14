"""M6 eval runner: >=10 scenarios -> deterministic checks + heuristic judge ->
rich table + JSON. Free-tier discipline: bounded scenarios, response cache
already in llm wrapper, no network without keys.
Run: python evals/run_evals.py [--only NAME] [--max N]"""
from __future__ import annotations

import glob
import json
import sys
import time

sys.path.insert(0, ".")

import yaml  # noqa: E402

from app.agent import tools as T  # noqa: E402
from app.agent.orchestrator import OrchestratorState  # noqa: E402
from app.engine.models import Household  # noqa: E402
from app.engine.planner import WEEK, generate_plan, load_recipes  # noqa: E402
from evals.checks import CHECKS, ENGINE_DEFAULT  # noqa: E402
from evals.judge import judge  # noqa: E402
from evals.sim_user import SimUser  # noqa: E402

RECIPES = load_recipes()
BY_ID = {r.id: r for r in RECIPES}


def run_check(name: str, st: OrchestratorState, params: dict):
    fn = CHECKS[name]
    try:
        try:
            return fn(st, BY_ID, params)
        except TypeError:
            return fn(st, BY_ID)
    except Exception as e:
        return False, f"check crashed: {e}"


def run_engine(sc: dict) -> dict:
    st = OrchestratorState(hid=f"hh-eval-{sc['name']}")
    st.household = Household.model_validate(sc["household"])
    st.plan = generate_plan(st.household, RECIPES, days=7, seed=sc.get("seed", 42))
    before = st.plan.model_dump_json()
    for d in sc.get("disruptions", []) or []:
        args = dict(d["args"])
        if args.get("day"):
            try:
                st.cook_day_index = WEEK.index(T.norm_day(args["day"]))
            except ValueError:
                pass
        T.dispatch(st, d["tool"], args)
    if sc.get("swap"):
        T.dispatch(st, "swap_meal", sc["swap"])
    T.dispatch(st, "build_grocery_list", {"seed": sc.get("grocery_seed", 42)})
    params = sc.get("params", {}) or {}
    if "plan_adapted" in (sc.get("checks") or []):
        params = {**params, "plan_adapted": {"before": before}}
    out = {}
    for name in sc.get("checks") or ENGINE_DEFAULT:
        ok, detail = run_check(name, st, params.get(name, {}))
        out[name] = {"pass": bool(ok), "detail": str(detail)[:220]}
    return {"name": sc["name"], "kind": "engine", "checks": out, "judge": {}}


def run_convo(sc: dict) -> dict:
    st = OrchestratorState(hid=f"hh-eval-{sc['name']}")
    user = SimUser(sc["conversation"])
    replies = []
    for t in user.turns():
        replies.append(st.handle_user(t))
    params = dict(sc.get("params", {}) or {})
    if "recovery" in (sc.get("checks") or []):
        params["recovery"] = {**params.get("recovery", {}), "replies": replies}
    out = {}
    for name in sc.get("checks") or []:
        if name == "plan_adapted":
            ok = bool(st.shortfalls) or _disruption_ok(st)
            out[name] = {"pass": ok, "detail": "shortfall queued or swap ok" if ok else "nothing adapted"}
            continue
        ok, detail = run_check(name, st, params.get(name, {}))
        out[name] = {"pass": bool(ok), "detail": str(detail)[:220]}
    jl = f"logs/eval_{sc['name']}.jsonl"
    with open(jl, "w", encoding="utf-8") as f:
        for e in st.transcript:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return {"name": sc["name"], "kind": "convo", "checks": out,
            "judge": judge(st.transcript), "replies": replies[-3:]}


def _disruption_ok(st: OrchestratorState) -> bool:
    for e in st.transcript:
        if e["role"] == "tool" and "report_disruption" in e["text"]:
            res = (e.get("tools") or [{}])[0].get("result", {})
            if res.get("ok") and (res.get("swapped") or res.get("shortfall")):
                return True
    return False


def main() -> int:
    only = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")]
    paths = sorted(glob.glob("evals/scenarios/*.yaml"))
    if only:
        paths = [p for p in paths if any(o in p for o in only)]
    results = []
    for p in paths:
        sc = yaml.safe_load(open(p, encoding="utf-8"))
        t0 = time.time()
        try:
            r = run_convo(sc) if sc.get("kind") == "convo" else run_engine(sc)
        except Exception as e:
            r = {"name": sc.get("name", p), "kind": "error", "checks": {},
                 "judge": {}, "error": str(e)[:200]}
        r["secs"] = round(time.time() - t0, 2)
        results.append(r)
    payload = {"ts": time.time(), "scenarios": results}
    fn = "evals/results_latest.json"
    json.dump(payload, open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # table
    all_checks = sorted({k for r in results for k in r.get("checks", {})})
    hdr = ["scenario"] + all_checks + ["judge"]
    rows = []
    for r in results:
        row = [r["name"][:22]]
        for c in all_checks:
            v = r.get("checks", {}).get(c)
            row.append("PASS" if v and v["pass"] else ("FAIL" if v else "-"))
        row.append(str(r.get("judge", {}).get("overall", "-")))
        rows.append(row)
    try:
        from rich.table import Table
        from rich.console import Console
        t = Table(title=f"M6 evals: {len(results)} scenarios")
        for h in hdr:
            t.add_column(h, overflow="fold")
        for row in rows:
            t.add_row(*[f"[red]{c}[/red]" if c == "FAIL" else c for c in row])
        Console().print(t)
    except ImportError:
        print("\t".join(hdr))
        for row in rows:
            print("\t".join(row))
    fails = [(r["name"], k, v["detail"]) for r in results
             for k, v in r.get("checks", {}).items() if not v["pass"]]
    print(f"\n{len(fails)} failing checks across {len(results)} scenarios.")
    for name, k, d in fails:
        print(f"  FAIL {name}::{k} — {d}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
