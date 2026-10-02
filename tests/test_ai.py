import os
import pytest
from backend.ai.gemma import GemmaArchitect, DEFAULT_GEMMA_MODEL, INTERACTIONS_API_URL
from backend.analyzer.analyzer import ProjectAnalyzer


@pytest.mark.asyncio
async def test_gemma_fallback_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMMA_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMMA_API_URL", raising=False)
    monkeypatch.delenv("GEMMA_MODEL", raising=False)

    architect = GemmaArchitect()
    assert not architect.is_configured()
    assert architect.model_name == DEFAULT_GEMMA_MODEL

    arch_data = {
        "project": "TestApp",
        "summary": {"total_types": 2, "controllers": 1, "services": 1, "repositories": 0, "entities": 0, "endpoints": 1, "relationships": 1},
        "controllers": [{
            "name": "OrderController",
            "package": "com.test",
            "dependencies": ["OrderService"],
            "endpoints": [{"http_method": "GET", "path": "/api/orders", "method_name": "listOrders", "return_type": "List", "controller": "OrderController"}]
        }],
        "services": [{
            "name": "OrderService",
            "package": "com.test",
            "dependencies": [],
            "implements": []
        }],
        "repositories": [],
        "entities": [],
        "relationships": [{"source": "OrderController", "target": "OrderService", "type": "dependency", "description": "injected"}]
    }

    # Test question about flow
    res_flow = await architect.ask("Explain the request flow", arch_data)
    assert "OrderController" in res_flow["answer"]
    assert "OrderService" in res_flow["answer"]
    assert "deterministic-rules-engine" in res_flow["model"]

    # Test question about endpoints
    res_ep = await architect.ask("List endpoints", arch_data)
    assert "/api/orders" in res_ep["answer"]
    assert "GET" in res_ep["answer"]


def test_api_key_and_model_configuration(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.delenv("GEMMA_API_KEY", raising=False)
    monkeypatch.setenv("GEMMA_MODEL", "gemma-4-31b-it")
    architect = GemmaArchitect()
    assert architect.api_key == "test-gemini-key"
    assert architect.model_name == "gemma-4-31b-it"
    assert architect.is_configured()

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMMA_API_KEY", "test-gemma-key")
    monkeypatch.delenv("GEMMA_MODEL", raising=False)
    architect2 = GemmaArchitect()
    assert architect2.api_key == "test-gemma-key"
    assert architect2.model_name == "gemma-4-26b-a4b-it"
    assert architect2.is_configured()


def test_live_interactions_api_request_construction(monkeypatch):
    """Verifies that the Google v1 Interactions API request contract is correctly constructed."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock-studio-api-key")
    monkeypatch.setenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")

    architect = GemmaArchitect()
    sample_arch = {
        "project": "DemoStore",
        "summary": {"total_types": 2, "controllers": 1, "services": 1, "repositories": 0, "entities": 0, "endpoints": 1, "relationships": 1},
        "controllers": [{
            "name": "CartController",
            "package": "com.store",
            "dependencies": ["CartService"],
            "endpoints": [{"http_method": "POST", "path": "/api/cart/add", "method_name": "addItem", "return_type": "Cart", "controller": "CartController"}]
        }],
        "services": [{"name": "CartService", "package": "com.store", "dependencies": []}],
        "repositories": [],
        "entities": [],
        "relationships": [{"source": "CartController", "target": "CartService", "type": "dependency"}]
    }

    req = architect.build_interactions_request("Explain the CartController dependencies", sample_arch)

    assert req["url"] == f"{INTERACTIONS_API_URL}?key=mock-studio-api-key"
    assert "https://generativelanguage.googleapis.com/v1/interactions" in req["url"]
    assert req["headers"]["Content-Type"] == "application/json"
    assert req["headers"]["x-goog-api-key"] == "mock-studio-api-key"

    payload = req["payload"]
    assert payload["model"] == "models/gemma-4-26b-a4b-it"
    assert len(payload["input"]) == 2
    assert payload["input"][0]["role"] == "system"
    assert "software architecture assistant" in payload["input"][0]["content"].lower()
    assert payload["input"][1]["role"] == "user"
    assert "CartController" in payload["input"][1]["content"]
    assert "Explain the CartController dependencies" in payload["input"][1]["content"]
    assert "generation_config" in payload


@pytest.mark.asyncio
async def test_gemma_direct_vs_indirect_dependency_answer():
    """Verify that assistant answers accurately about direct vs indirect dependencies."""
    architect = GemmaArchitect()
    sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample-project")
    arch = ProjectAnalyzer(sample_dir).analyze().model_dump()

    # Question: Does UserController directly depend on UserRepository?
    res = await architect.ask("Does UserController directly depend on UserRepository?", arch)
    answer = res["answer"]

    assert "No" in answer or "not directly depend" in answer
    assert "UserService" in answer
    assert "UserRepository" in answer


@pytest.mark.asyncio
async def test_gemma_absent_components_grounded_answer():
    """Verify that questions about non-existent components return grounded not-found answers."""
    architect = GemmaArchitect()
    sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample-project")
    arch = ProjectAnalyzer(sample_dir).analyze().model_dump()

    # Test query about authentication
    res_auth = await architect.ask("What authentication or JWT mechanisms are used?", arch)
    assert res_auth["answer"] == "No such component was detected in the analyzed architecture."

    # Test query about payment service
    res_pay = await architect.ask("Explain the payment gateway integration", arch)
    assert res_pay["answer"] == "No such component was detected in the analyzed architecture."

    # Test query about database vendor
    res_db = await architect.ask("Which database vendor is configured (PostgreSQL, MySQL)?", arch)
    assert res_db["answer"] == "The extracted architecture does not provide enough information to determine the database vendor."


@pytest.mark.asyncio
async def test_gemma_observations_grounded_answer():
    """Verify that questions about architectural issues answer strictly from detected observations."""
    architect = GemmaArchitect()
    sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample-project")
    arch = ProjectAnalyzer(sample_dir).analyze().model_dump()

    res = await architect.ask("What architectural issues exist?", arch)
    assert "UserController" in res["answer"]
    assert "exposes the User entity directly in 3 endpoints" in res["answer"]
    assert "consider returning UserDTO" in res["answer"]


@pytest.mark.asyncio
async def test_gemma_runtime_behavior_grounded_answer():
    """Verify that runtime method-body queries are recognized as out-of-scope for static analysis."""
    architect = GemmaArchitect()
    sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample-project")
    arch = ProjectAnalyzer(sample_dir).analyze().model_dump()

    res = await architect.ask("What happens when GET /api/users/{id} finds no user in database?", arch)
    assert "cannot be determined from the extracted static architecture metadata" in res["answer"]


def test_gemma_privacy_no_raw_source_code():
    """Verify that only structured metadata is prepared for Gemma, never raw Java source code."""
    architect = GemmaArchitect()
    sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample-project")
    arch = ProjectAnalyzer(sample_dir).analyze().model_dump()

    req = architect.build_interactions_request("Explain architecture", arch)
    user_payload_content = req["payload"]["input"][1]["content"]

    # Must contain structural metadata
    assert "UserController" in user_payload_content
    assert "GET" in user_payload_content
    assert "/api/users" in user_payload_content

    # Must NOT contain raw source code strings / implementation blocks
    assert "public class UserController" not in user_payload_content
    assert "ResponseEntity.ok(userService.getAllUsers())" not in user_payload_content
    assert "public static void main" not in user_payload_content
    assert "package com.example.demo;" not in user_payload_content


@pytest.mark.asyncio
async def test_gemma_provider_failure_resilience():
    architect = GemmaArchitect()
    architect.api_key = "invalid-dummy-key"
    architect.api_url = "http://localhost:99999/invalid-endpoint"

    arch_data = {
        "project": "TestApp",
        "summary": {"total_types": 1, "controllers": 1, "services": 0, "repositories": 0, "entities": 0, "endpoints": 0, "relationships": 0},
        "controllers": [{"name": "DemoController", "package": "com.demo", "dependencies": [], "endpoints": []}],
        "services": [],
        "repositories": [],
        "entities": [],
        "relationships": []
    }

    res = await architect.ask("Explain DemoController", arch_data)
    assert "answer" in res
    assert "DemoController" in res["answer"]
