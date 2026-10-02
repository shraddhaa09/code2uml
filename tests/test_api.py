import io
import os
import zipfile
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Code2UML AI"


def test_analyze_sample_endpoint():
    response = client.post("/api/analyze/sample")
    assert response.status_code == 200
    data = response.json()
    assert "architecture" in data
    assert "mermaid" in data
    assert "mermaid_full" in data
    assert "mermaid_uml" in data
    assert data["architecture"]["summary"]["controllers"] >= 1
    assert data["architecture"]["summary"]["services"] >= 1
    assert data["architecture"]["summary"]["repositories"] >= 1


def test_analyze_valid_zip_upload():
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as z:
        z.writestr(
            "com/test/AccountController.java",
            """
            package com.test;
            import org.springframework.web.bind.annotation.*;
            @RestController
            @RequestMapping("/accounts")
            public class AccountController {
                @GetMapping
                public String list() { return "ok"; }
            }
            """
        )
    zip_buffer.seek(0)

    files = {"file": ("project.zip", zip_buffer.getvalue(), "application/zip")}
    response = client.post("/api/analyze", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["architecture"]["summary"]["controllers"] == 1
    assert "AccountController" in data["mermaid"]


def test_analyze_empty_zip_fails():
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as z:
        pass  # empty zip
    zip_buffer.seek(0)

    files = {"file": ("empty.zip", zip_buffer.getvalue(), "application/zip")}
    response = client.post("/api/analyze", files=files)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_analyze_invalid_corrupted_zip_fails():
    files = {"file": ("corrupt.zip", b"not-a-valid-zip-content", "application/zip")}
    response = client.post("/api/analyze", files=files)
    assert response.status_code == 400


def test_analyze_zip_without_java_files_fails():
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as z:
        z.writestr("readme.txt", "just a text file")
    zip_buffer.seek(0)

    files = {"file": ("nojava.zip", zip_buffer.getvalue(), "application/zip")}
    response = client.post("/api/analyze", files=files)
    assert response.status_code == 400
    assert "no java source files" in response.json()["detail"].lower()


def test_analyze_zip_slip_attempt_fails():
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as z:
        z.writestr("../../etc/malicious.txt", "evil")
    zip_buffer.seek(0)

    files = {"file": ("slip.zip", zip_buffer.getvalue(), "application/zip")}
    response = client.post("/api/analyze", files=files)
    assert response.status_code == 400
    assert "path traversal" in response.json()["detail"].lower()


def test_chat_endpoint_with_architecture():
    sample_arch = {
        "project": "Demo",
        "summary": {"total_classes": 3, "controllers": 1, "services": 1, "repositories": 1},
        "controllers": [{"name": "UserController", "package": "com.example", "dependencies": ["UserService"], "endpoints": []}],
        "services": [{"name": "UserService", "package": "com.example", "dependencies": ["UserRepository"]}],
        "repositories": [{"name": "UserRepository", "package": "com.example", "dependencies": ["User"]}],
        "entities": [{"name": "User", "fields": []}],
        "relationships": [{"source": "UserController", "target": "UserService", "type": "dependency"}]
    }

    payload = {
        "question": "What is the request flow?",
        "architecture": sample_arch
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert len(data["answer"]) > 10
