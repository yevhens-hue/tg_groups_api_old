from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="TG API", docs_url="/docs", openapi_url="/openapi.json")

@app.get("/health")
def health():
    return {"status":"ok"}

class SearchRequest(BaseModel):
    query: str
    limit: int = 20

@app.post("/search_groups")
def search_groups(req: SearchRequest):
    return {"ok": True, "query": req.query, "items": []}
