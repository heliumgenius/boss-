"""FastAPI web application for boss-cli Web UI."""

from __future__ import annotations

import json
import time
from pathlib import Path
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ..auth import load_credential
from ..client.transport import BossClient
from ..exceptions import BossApiError
from .parser import parse_query

HERE = Path(__file__).parent
INDEX_HTML = (HERE / "templates" / "index.html").read_text(encoding="utf-8")


def create_app() -> FastAPI:
    app = FastAPI(title="Boss CLI Web UI")

    static_dir = HERE / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTMLResponse(INDEX_HTML)

    @app.post("/search", response_class=HTMLResponse)
    async def search(query: str = Form(...)):
        params = parse_query(query)
        cred = load_credential()
        if not cred:
            return HTMLResponse('<div class="error">未登录，请先在终端执行 boss login</div>')

        city_code = None
        if params["city"]:
            from ..constants import CITY_CODES
            city_code = CITY_CODES.get(params["city"])

        salary_code = None
        if params["salary"]:
            from ..constants import SALARY_CODES
            salary_code = SALARY_CODES.get(params["salary"])

        exp_code = None
        if params["experience"]:
            from ..constants import EXP_CODES
            exp_code = EXP_CODES.get(params["experience"])

        degree_code = None
        if params["degree"]:
            from ..constants import DEGREE_CODES
            degree_code = DEGREE_CODES.get(params["degree"])

        try:
            with BossClient(cred) as client:
                data = client.search_jobs(
                    query=params["keyword"] or "",
                    city=city_code or "100010000",
                    experience=exp_code,
                    degree=degree_code,
                    salary=salary_code,
                )
        except BossApiError as e:
            return HTMLResponse(f'<div class="error">搜索失败: {e}</div>')

        job_list = data.get("jobList", [])
        lid = data.get("lid", "")

        rows = ""
        for i, job in enumerate(job_list, 1):
            name = job.get("jobName", "-")
            company = job.get("brandName", "-")
            salary_text = job.get("salaryDesc", "-")
            exp_text = job.get("jobExperience", "-")
            degree_text = job.get("jobDegree", "-")
            sec_id = job.get("securityId", "")
            rows += f"""<tr>
                <td><input type="checkbox" class="job-check" value="{sec_id}" data-lid="{lid}"></td>
                <td>{i}</td>
                <td>{name}</td>
                <td>{company}</td>
                <td>{salary_text}</td>
                <td>{exp_text}</td>
                <td>{degree_text}</td>
            </tr>"""

        return HTMLResponse(rows)

    @app.post("/batch-greet")
    async def batch_greet(data: dict):
        ids = data.get("ids", [])
        lid = data.get("lid", "")

        cred = load_credential()
        if not cred:
            return {"error": "not authenticated"}

        async def event_stream():
            yield f"event: start\ndata: {json.dumps({'total': len(ids)})}\n\n"
            success = 0
            fail = 0
            for i, sec_id in enumerate(ids):
                try:
                    with BossClient(cred) as client:
                        client.add_friend(security_id=sec_id, lid=lid)
                    success += 1
                    yield f"event: progress\ndata: {json.dumps({'index': i + 1, 'security_id': sec_id, 'status': 'ok'})}\n\n"
                except BossApiError as e:
                    fail += 1
                    yield f"event: progress\ndata: {json.dumps({'index': i + 1, 'security_id': sec_id, 'status': 'fail', 'message': str(e)})}\n\n"
                time.sleep(1.5)
            yield f"event: complete\ndata: {json.dumps({'success': success, 'fail': fail})}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return app


app = create_app()
