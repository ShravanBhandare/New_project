import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from src.api.routers import companies, screener, peers, sectors, reports, health

app = FastAPI(
    title="Nifty 100 Financial Intelligence Platform API",
    description="REST API for fundamentally analyzing Nifty 100 constituent companies, financial statements, ratios, peer groups, and downloading print-ready tearsheets.",
    version="1.0.0"
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers under /api/v1 prefix
app.include_router(companies.router, prefix="/api/v1")
app.include_router(screener.router, prefix="/api/v1")
app.include_router(peers.router, prefix="/api/v1")
app.include_router(sectors.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")

@app.get("/", include_in_schema=False)
def root():
    """Redirect root access to Swagger API documentation."""
    return RedirectResponse(url="/docs")

if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
