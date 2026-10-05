import os
import shutil
import tempfile
import zipfile
from typing import Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from backend.analyzer.analyzer import ProjectAnalyzer
from backend.diagram.mermaid import MermaidGenerator
from backend.ai.gemma import GemmaArchitect

app = FastAPI(
    title="Code2UML AI Backend",
    description="Deterministic Spring Boot Architecture Analyzer & Gemma AI Assistant",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

gemma_architect = GemmaArchitect()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
SAMPLE_PROJECT_DIR = os.path.join(BASE_DIR, "sample-project")


class ChatRequest(BaseModel):
    question: str
    architecture: Dict[str, Any]
    analysis_id: Optional[str] = None


def validate_and_extract_zip(zip_file_bytes: bytes, extract_to: str) -> None:
    """Extract zip safely preventing zip-slip path traversal, nested recursion, and zip bombs."""
    import io
    MAX_UNCOMPRESSED_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_ZIP_ENTRIES = 2000

    try:
        with zipfile.ZipFile(io.BytesIO(zip_file_bytes)) as z:
            infolist = z.infolist()
            if not infolist:
                raise HTTPException(status_code=400, detail="The uploaded ZIP file is empty.")

            if len(infolist) > MAX_ZIP_ENTRIES:
                raise HTTPException(status_code=400, detail=f"ZIP contains {len(infolist)} entries, exceeding maximum safety limit of {MAX_ZIP_ENTRIES}.")

            total_uncompressed_size = 0
            resolved_extract_to = os.path.abspath(extract_to)

            for member in infolist:
                total_uncompressed_size += member.file_size
                if total_uncompressed_size > MAX_UNCOMPRESSED_SIZE:
                    raise HTTPException(status_code=400, detail=f"Total uncompressed ZIP size exceeds safety limit of {MAX_UNCOMPRESSED_SIZE // (1024 * 1024)}MB.")

                # Zip-slip check
                member_path = os.path.abspath(os.path.join(extract_to, member.filename))
                if not member_path.startswith(resolved_extract_to):
                    raise HTTPException(status_code=400, detail=f"Illegal path traversal detected in ZIP: {member.filename}")

            # Extract all files safely
            z.extractall(extract_to)
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid or corrupted ZIP file.")


@app.get("/api/health")
async def health_check():
    deployment_mode = os.getenv("DEPLOYMENT_MODE", "local").lower().strip()
    return {
        "status": "healthy",
        "service": "Code2UML AI",
        "ai_enabled": gemma_architect.is_configured(),
        "ai_configured": gemma_architect.is_configured(),
        "ai_model": gemma_architect.model_name,
        "deployment_mode": deployment_mode
    }


@app.post("/api/analyze")
async def analyze_zip(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are supported.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File size exceeds maximum limit of 50MB.")

    with tempfile.TemporaryDirectory(prefix="code2uml_") as temp_dir:
        validate_and_extract_zip(content, temp_dir)
        
        project_name = os.path.splitext(file.filename)[0]
        analyzer = ProjectAnalyzer(temp_dir, project_name=project_name)
        architecture = analyzer.analyze()

        if architecture.summary.total_classes == 0:
            raise HTTPException(status_code=400, detail="No Java source files (.java) found in the uploaded archive.")

        mermaid_code = MermaidGenerator.generate(architecture, mode="default")
        mermaid_full = MermaidGenerator.generate(architecture, mode="full")
        mermaid_uml = MermaidGenerator.generate_uml(architecture)

        return {
            "analysis_id": architecture.analysis_id,
            "architecture": architecture.model_dump(),
            "mermaid": mermaid_code,
            "mermaid_full": mermaid_full,
            "mermaid_uml": mermaid_uml
        }


@app.post("/api/analyze/sample")
async def analyze_sample():
    """Direct analysis endpoint for the built-in sample project."""
    if not os.path.exists(SAMPLE_PROJECT_DIR):
        raise HTTPException(status_code=404, detail="Sample project not found on server.")

    analyzer = ProjectAnalyzer(SAMPLE_PROJECT_DIR, project_name="Sample Spring Boot Demo")
    architecture = analyzer.analyze()
    mermaid_code = MermaidGenerator.generate(architecture, mode="default")
    mermaid_full = MermaidGenerator.generate(architecture, mode="full")
    mermaid_uml = MermaidGenerator.generate_uml(architecture)

    return {
        "analysis_id": architecture.analysis_id,
        "architecture": architecture.model_dump(),
        "mermaid": mermaid_code,
        "mermaid_full": mermaid_full,
        "mermaid_uml": mermaid_uml
    }


@app.post("/api/chat")
async def chat_about_architecture(payload: ChatRequest):
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    arch_id = payload.architecture.get("analysis_id")
    if payload.analysis_id and arch_id and payload.analysis_id != arch_id:
        raise HTTPException(status_code=400, detail="Stale chat request: analysis_id does not match the active project architecture.")

    response = await gemma_architect.ask(payload.question, payload.architecture)
    return response


# Mount frontend static files
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
