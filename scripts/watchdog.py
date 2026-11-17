"""Hourly check that the Mac mini is still checking the India boards. If its last finished board check is more
than 2 hours old, one comment goes on the "Daily health report" issue (the GitHub app notifies you); no repeat
while the same outage goes on (at most one alert every 12 hours)."""
from __future__ import annotations

import datetime as dt

from health import IST, NOW, gh, ts

LIMIT_H, QUIET_H = 2, 12


def publishing() -> None:
    """Publishing must not stop silently: alert if the last 2 'Prepare' runs failed, or nothing went live for 6 hours
    while the Mac keeps finding new notices."""
    from alert import send
    runs = (gh("GET", "/actions/workflows/prepare.yml/runs", params={"status": "completed", "per_page": 6}) or {}).get("workflow_runs", [])
    done = [r for r in runs if r.get("conclusion") in ("success", "failure")]
    if len(done) >= 2 and all(r["conclusion"] == "failure" for r in done[:2]):
        send("prepare-failing", "Publishing is failing: the last 2 'Prepare notices' runs crashed, so new notices are NOT going live.")
        return
    ok = [r for r in done if r["conclusion"] == "success"]
    found = (gh("GET", "/actions/workflows/watch-india.yml/runs", params={"status": "success", "per_page": 1}) or {}).get("workflow_runs", [])
    if ok and found and NOW - ts(ok[0]["updated_at"]) > dt.timedelta(hours=6) and NOW - ts(found[0]["updated_at"]) < dt.timedelta(hours=2):
        send("prepare-stalled", "Nothing has been published for 6 hours although the Mac is checking the boards.")


def main() -> None:
    try:
        publishing()
    except Exception as e:   # the Mac check below must still run
        print("publishing check failed:", e)
    runs = (gh("GET", "/actions/workflows/watch-india.yml/runs", params={"status": "success", "per_page": 1}) or {}).get("workflow_runs", [])
    last = ts(runs[0]["updated_at"]) if runs else None
    if last and NOW - last < dt.timedelta(hours=LIMIT_H):
        print(f"ok: last India board check {last.astimezone(IST):%d %b %H:%M} IST")
        return
    # while the Mac is away, check the boards GitHub can reach (SSC, NTA, UPPSC, BPSC, BSSC, SBI, LIC, ISRO) every hour
    # instead of every 3 hours, so the biggest central boards keep flowing
    gh("POST", "/actions/workflows/watch.yml/dispatches", json={"ref": "main"})
    found = gh("GET", "/issues", params={"state": "open", "labels": "health", "per_page": 1}) or []
    if not found:
        print("no health issue"); return
    num = found[0]["number"]
    since = (NOW - dt.timedelta(hours=QUIET_H)).isoformat()
    recent = gh("GET", f"/issues/{num}/comments", params={"since": since, "per_page": 50}) or []
    if any("Mac mini has stopped" in (c.get("body") or "") for c in recent):
        print("already alerted"); return
    when = f"{last.astimezone(IST):%d %b %H:%M} IST" if last else "unknown"
    gh("POST", f"/issues/{num}/comments", json={"body":
        f"**Mac mini has stopped checking the boards.** Last finished check: {when}. "
        "No new notices go live until it is back. Wake the Mac (or check its internet); the runner starts by itself."})
    print("alert sent")


if __name__ == "__main__":
    main()
