import os
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel, Field

app = FastAPI(title="SoulPainterMinis API", description="Backend for commission inquiries and site utilities.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ContactPayload(BaseModel):
    name: str = Field(...)
    email: str = Field(...)
    description: str = Field(...)
    tier: Optional[str] = Field(default=None)
    addons: List[str] = Field(default_factory=list)


@app.get("/")
def read_root():
    return {"message": "SoulPainterMinis API running"}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        from database import db
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, 'name', None) or "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except ImportError:
        response["database"] = "❌ Database module not found"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


@app.post("/api/contact")
async def submit_contact(
    name: str = Form(...),
    email: str = Form(...),
    description: str = Form(...),
    tier: Optional[str] = Form(None),
    addons: Optional[str] = Form(None),  # comma-separated list
    files: Optional[List[UploadFile]] = File(None)
):
    """Accept commission inquiries with optional reference image uploads.
    Files are not persisted to storage in this demo; filenames and sizes are recorded.
    """
    try:
        from database import create_document
    except Exception:
        create_document = None

    addons_list = [a.strip() for a in (addons or '').split(',') if a.strip()]
    file_info = []
    if files:
        for f in files:
            try:
                chunk = await f.read()
                size = len(chunk)
                await f.close()
                file_info.append({"filename": f.filename, "content_type": f.content_type, "size": size})
            except Exception:
                file_info.append({"filename": f.filename, "content_type": f.content_type, "size": None})

    payload = {
        "name": name,
        "email": email,
        "description": description,
        "tier": tier,
        "addons": addons_list,
        "files": file_info,
        "source": "website",
    }

    inserted_id = None
    if create_document:
        try:
            inserted_id = create_document("contactrequest", payload)
        except Exception:
            inserted_id = None

    return JSONResponse({"ok": True, "message": "Thanks! We'll get back to you within 24-48 hours.", "id": inserted_id, "received": payload})


class EstimateRequest(BaseModel):
    box_price: float
    tier: str
    addons: List[str] = Field(default_factory=list)


@app.post("/api/estimate")
def estimate(req: EstimateRequest):
    base_multiplier = 2 if req.tier.lower() == "shikai" else 4
    total = req.box_price * base_multiplier
    addon_map = {
        "OSL Effects": 0.2,
        "Weathering / Battle Damage": 0.15,
        "Advanced Basing": 0.15,
        "Fine Freehand Details": 0.25,
        "Conversions / Kitbashing": 0.3,
        "Magnetization": 0.1,
    }
    for a in req.addons:
        total += req.box_price * addon_map.get(a, 0)
    return {"estimated_total": round(total, 2)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
