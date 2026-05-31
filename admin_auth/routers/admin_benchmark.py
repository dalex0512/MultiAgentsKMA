import json
import logging
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from admin_auth.auth.admin_guard import require_dean
from admin_auth.core.config import settings
from admin_auth.models.user_minimal import User

log = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/benchmark", tags=["admin-benchmark"])

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "eval" / "benchmark.json"
RESULTS_DIR = ROOT / "eval" / "results"

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


class BenchmarkStartRequest(BaseModel):
    tier: str = ""
    limit: int = 5
    base_url: str = "http://127.0.0.1:8000"


def _run_benchmark_job(job_id: str, tier: str, limit: int, base_url: str) -> None:
    with _lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()

    cmd = [
        sys.executable,
        str(ROOT / "eval" / "run_benchmark.py"),
        "--base-url",
        base_url,
        "--limit",
        str(limit),
    ]
    if tier:
        cmd.extend(["--tier", tier])

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3600,
        )
        with _lock:
            _jobs[job_id]["returncode"] = proc.returncode
            _jobs[job_id]["stdout"] = proc.stdout[-8000:] if proc.stdout else ""
            _jobs[job_id]["stderr"] = proc.stderr[-4000:] if proc.stderr else ""
            if proc.returncode != 0:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = proc.stderr or "Benchmark exited with error"
            else:
                _jobs[job_id]["status"] = "done"
    except subprocess.TimeoutExpired:
        with _lock:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = "Timeout 60 phút"
    except Exception as e:
        log.exception("benchmark job")
        with _lock:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(e)

    results = sorted(RESULTS_DIR.glob("run_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if results:
        with _lock:
            _jobs[job_id]["result_file"] = results[0].name
            try:
                _jobs[job_id]["summary"] = json.loads(
                    results[0].read_text(encoding="utf-8")
                )
            except Exception:
                pass

    with _lock:
        _jobs[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()


@router.get("/runs")
def list_benchmark_runs(_: User = Depends(require_dean)):
    if not RESULTS_DIR.is_dir():
        return {"runs": []}
    files = sorted(RESULTS_DIR.glob("run_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]
    runs = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            runs.append({
                "file": f.name,
                "run_at": data.get("run_at"),
                "pass_rate": data.get("pass_rate"),
                "passed": data.get("passed"),
                "total": data.get("total"),
                "partial": data.get("partial", False),
            })
        except Exception:
            runs.append({"file": f.name, "error": "parse_failed"})
    return {"runs": runs}


@router.get("/runs/{filename}")
def get_benchmark_run(filename: str, _: User = Depends(require_dean)):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = RESULTS_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("/start")
def start_benchmark(
    body: BenchmarkStartRequest,
    background_tasks: BackgroundTasks,
    _: User = Depends(require_dean),
):
    if not BENCHMARK.is_file():
        raise HTTPException(status_code=400, detail="Chưa có eval/benchmark.json")

    limit = max(1, min(body.limit, settings.ADMIN_BENCHMARK_MAX_CASES))
    job_id = str(uuid.uuid4())[:8]
    with _lock:
        _jobs[job_id] = {
            "id": job_id,
            "status": "queued",
            "tier": body.tier or "all",
            "limit": limit,
            "base_url": body.base_url,
        }

    background_tasks.add_task(_run_benchmark_job, job_id, body.tier.strip(), limit, body.base_url.strip())
    return {"job_id": job_id, "status": "queued", "limit": limit}


@router.get("/jobs/{job_id}")
def get_benchmark_job(job_id: str, _: User = Depends(require_dean)):
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    return job
