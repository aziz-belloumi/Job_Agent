"""FastAPI application factory and static file serving for JobAgent."""

import logging
import sys
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from jobagent.api.routes import router

logger = logging.getLogger("jobagent.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="JobAgent", version="1.0.0")
app.include_router(router)

DIST_DIR = Path(__file__).resolve().parents[1] / "web" / "dist"
INDEX_FILE = DIST_DIR / "index.html"


@app.on_event("startup")
def on_startup() -> None:
    """Log server startup details."""
    logger.info("JobAgent Web API starting on http://127.0.0.1:8000")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled errors, log to stderr without leaking traces to clients."""
    print(f"Unhandled error on {request.method} {request.url.path}: {exc}", file=sys.stderr)
    return JSONResponse(
        status_code=500,
        content={"error": "An internal server error occurred", "detail": str(exc)},
    )


if INDEX_FILE.exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="static")
else:
    @app.get("/", response_class=HTMLResponse)
    def fallback_page() -> str:
        """Friendly fallback page when the React frontend is not yet built."""
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>JobAgent — Build Frontend</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                       display: flex; justify-content: center; align-items: center; min-height: 100vh;
                       background: #0f172a; color: #f8fafc; margin: 0; }
                .card { background: #1e293b; padding: 2rem; border-radius: 8px; max-width: 500px;
                        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); border: 1px solid #334155; }
                h1 { margin-top: 0; color: #38bdf8; font-size: 1.5rem; }
                code { background: #0f172a; padding: 0.2rem 0.4rem; border-radius: 4px; color: #38bdf8; }
                pre { background: #0f172a; padding: 1rem; border-radius: 6px; overflow-x: auto; color: #a5f3fc; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>JobAgent Frontend Not Built</h1>
                <p>The React web UI has not been compiled yet.</p>
                <p>To compile the frontend, run:</p>
                <pre>cd jobagent/web
npm install
npm run build</pre>
                <p>Then refresh this page. The API is active at <code>/api/*</code>.</p>
            </div>
        </body>
        </html>
        """
