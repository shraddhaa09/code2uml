"""
Tests for large project analysis, Mermaid stability, dynamic chat intent routing,
authentication/database detection, analyzer heuristics, and Gemma grounding.
"""

import os
import re
import pytest
import tempfile
import shutil
from fastapi.testclient import TestClient

from backend.main import app, validate_and_extract_zip
from backend.analyzer.analyzer import ProjectAnalyzer
from backend.diagram.mermaid import MermaidGenerator
from backend.ai.gemma import GemmaArchitect
from tests.fixtures.make_large_project import (
    create_large_project_dir,
    create_large_project_zip_bytes
)

client = TestClient(app)


@pytest.fixture(scope="module")
def large_project_fixture():
    """Generates the ~90-type synthetic Spring Boot project in a temp directory."""
    tmp_dir = tempfile.mkdtemp(prefix="test_large_spring_")
    create_large_project_dir(tmp_dir)
    analyzer = ProjectAnalyzer(tmp_dir, project_name="Large Enterprise Project")
    arch = analyzer.analyze()
    yield tmp_dir, arch
    shutil.rmtree(tmp_dir, ignore_errors=True)


# ==============================================================================
# BUG 1: MERMAID ON LARGE PROJECTS & FOCUS MODE
# ==============================================================================

def test_mermaid_generation_on_large_project(large_project_fixture):
    """Verify that default, full, and focus Mermaid diagrams are generated without syntax crashes."""
    _, arch = large_project_fixture

    # Assert expected scale
    assert arch.summary.total_types >= 80
    assert arch.summary.relationships >= 100
    assert arch.summary.endpoints == 30
    assert arch.summary.entities == 14
    assert arch.summary.repositories == 14

    # Generate default (structural)
    m_default = MermaidGenerator.generate(arch, mode="default")
    assert "flowchart TD" in m_default
    assert "ControllersLayer" in m_default
    assert "ServicesLayer" in m_default
    assert "RepositoriesLayer" in m_default
    assert "EntitiesLayer" in m_default

    # Generate full (all edges)
    m_full = MermaidGenerator.generate(arch, mode="full")
    assert "flowchart TD" in m_full
    assert len(m_full) > len(m_default)

    # Generate UML classDiagram
    m_uml = MermaidGenerator.generate_uml(arch)
    assert "classDiagram" in m_uml
    assert "class OrderController" in m_uml
    assert "class PaymentStrategy" in m_uml

    # Generate Focus Mode for a specific controller (e.g. AuthController or OrderController)
    m_focus = MermaidGenerator.generate_focus(arch, "AuthController")
    assert "flowchart TD" in m_focus
    assert "AuthController" in m_focus
    assert "AuthService" in m_focus


# ==============================================================================
# BUG 2 & BUG 3: CHAT INTENT ROUTING & DYNAMIC RESOLUTION
# ==============================================================================

def test_chat_no_hardcoded_sample_names(large_project_fixture):
    """Chat must not return hardcoded sample-project names when querying the large project."""
    _, arch = large_project_fixture
    arch_dict = arch.model_dump()
    architect = GemmaArchitect()

    # Query help / greeting
    ans_help = architect._deterministic_answer("help", arch_dict)
    assert "UserController" not in ans_help or "UserController" in [c.name for c in arch.classes]
    # Check that overview or help does not assume 7 types
    ans_overview = architect._deterministic_answer("overview of the project", arch_dict)
    assert str(arch.summary.total_types) in ans_overview


def test_chat_resolve_non_existent_class(large_project_fixture):
    """When a non-existent class is queried, the chat must explicitly report it was not found."""
    _, arch = large_project_fixture
    arch_dict = arch.model_dump()
    architect = GemmaArchitect()

    # Query class that does not exist in the project
    ans = architect._deterministic_answer("Does NonExistentService connect to NonExistentRepo?", arch_dict)
    assert "not found in the analyzed architecture" in ans.lower() or "not found" in ans.lower()
    assert "NonExistentService" in ans


def test_chat_intent_entities_and_repositories(large_project_fixture):
    """'What database entities and repositories are present?' must list entities and repositories."""
    _, arch = large_project_fixture
    arch_dict = arch.model_dump()
    architect = GemmaArchitect()

    q = "What database entities and repositories are present?"
    ans = architect._deterministic_answer(q, arch_dict)

    assert "User" in ans
    assert "Order" in ans
    assert "UserRepository" in ans
    assert "OrderRepository" in ans
    assert "Based on analyzed files" in ans


def test_chat_intent_endpoints_list(large_project_fixture):
    """List all endpoints or endpoints for a specific controller."""
    _, arch = large_project_fixture
    arch_dict = arch.model_dump()
    architect = GemmaArchitect()

    # All endpoints
    ans_all = architect._deterministic_answer("List all REST endpoints", arch_dict)
    assert "/api/auth/login" in ans_all
    assert "/api/orders" in ans_all

    # Controller-specific endpoints
    ans_ctrl = architect._deterministic_answer("What endpoints are in AuthController?", arch_dict)
    assert "/api/auth/login" in ans_ctrl
    assert "/api/auth/register" in ans_ctrl


def test_chat_intent_dependency_path_and_flow(large_project_fixture):
    """Verify dependency path graph search between two classes."""
    _, arch = large_project_fixture
    arch_dict = arch.model_dump()
    architect = GemmaArchitect()

    # Direct / indirect dependency path
    ans_path = architect._deterministic_answer("Does OrderController depend on OrderRepository?", arch_dict)
    assert "OrderController" in ans_path
    assert "OrderRepository" in ans_path
    # Should explain direct vs indirect path
    assert "OrderService" in ans_path

    # Implementers of an interface
    ans_impl = architect._deterministic_answer("Who implements PaymentStrategy?", arch_dict)
    assert "CreditCardPaymentStrategy" in ans_impl
    assert "PaypalPaymentStrategy" in ans_impl
    assert "CryptoPaymentStrategy" in ans_impl


# ==============================================================================
# BUG 4: AUTHENTICATION & DATABASE VENDOR DETECTION
# ==============================================================================

def test_database_vendor_detection_with_evidence(large_project_fixture):
    """Database vendor must be detected from pom.xml and application.properties."""
    tmp_dir, arch = large_project_fixture
    arch_dict = arch.model_dump()
    architect = GemmaArchitect()

    ans = architect._deterministic_answer("Which database vendor is used?", arch_dict)
    assert "PostgreSQL" in ans
    assert "Based on analyzed files" in ans or "pom.xml" in ans or "application.properties" in ans


def test_authentication_detection_with_evidence(large_project_fixture):
    """Authentication components must be detected from SecurityConfig, filters, and pom.xml."""
    _, arch = large_project_fixture
    arch_dict = arch.model_dump()
    architect = GemmaArchitect()

    ans = architect._deterministic_answer("Is there an authentication component?", arch_dict)
    assert "SecurityConfig" in ans or "Jwt" in ans or "spring-boot-starter-security" in ans or "AuthService" in ans
    assert "Based on analyzed files" in ans


# ==============================================================================
# BUG 5: ANALYZER CORRECTNESS (PACKAGES, WARNINGS, DTO HEURISTICS)
# ==============================================================================

def test_package_counting_default_package(tmp_path):
    """Projects with classes in default package must have packages count >= 1."""
    f1 = tmp_path / "MyClass.java"
    f1.write_text("public class MyClass {}", encoding="utf-8")

    analyzer = ProjectAnalyzer(str(tmp_path))
    arch = analyzer.analyze()

    assert arch.summary.packages == 1
    assert arch.packages == ["(default)"]


def test_no_spring_components_warning(tmp_path):
    """Non-Spring Java project must generate a warning in diagnostics."""
    f1 = tmp_path / "com" / "example" / "Calculator.java"
    f1.parent.mkdir(parents=True)
    f1.write_text("package com.example;\npublic class Calculator { public int add(int a, int b) { return a + b; } }", encoding="utf-8")

    analyzer = ProjectAnalyzer(str(tmp_path))
    arch = analyzer.analyze()

    assert any("No Spring Boot components detected" in w for w in arch.diagnostics.warnings)


def test_dto_record_and_heuristic_classification(large_project_fixture):
    """Verify records and heuristic DTOs are classified as DTOs."""
    _, arch = large_project_fixture
    dto_names = {d.name for d in arch.dtos}
    assert "LoginRequest" in dto_names
    assert "UserDTO" in dto_names
    assert "OrderCreateRequest" in dto_names


def test_service_interface_no_implementation_observation_false_positives(large_project_fixture):
    """PaymentStrategy has 3 @Component implementers; it must NOT be flagged as un-implemented."""
    _, arch = large_project_fixture
    unimplemented_obs = [obs.message for obs in arch.observations if "has no implementing class" in obs.message]
    assert not any("PaymentStrategy" in msg for msg in unimplemented_obs)
    assert not any("UserService" in msg for msg in unimplemented_obs)


# ==============================================================================
# BUG 6 & BUG 7: GEMMA GROUNDING, HEALTH API & DEPLOYMENT MODE
# ==============================================================================

def test_health_endpoint_fields(monkeypatch):
    """Health endpoint must expose ai_enabled, ai_model, and deployment_mode."""
    monkeypatch.setenv("DEPLOYMENT_MODE", "hosted")
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert "ai_configured" in data
    assert "ai_model" in data
    assert data.get("deployment_mode") == "hosted"


def test_api_chat_analysis_id_and_validation(large_project_fixture):
    """Chat API endpoint must validate analysis_id and return evidence."""
    _, arch = large_project_fixture
    arch_dict = arch.model_dump()

    res = client.post("/api/chat", json={
        "question": "What entities are in the project?",
        "architecture": arch_dict,
        "analysis_id": arch.analysis_id
    })
    assert res.status_code == 200
    data = res.json()
    assert "User" in data["answer"]
    assert "model" in data


def test_property_chat_answers_class_names_exist_or_reported_missing(large_project_fixture):
    """Property test on the large fixture: every class name in a chat answer exists in the architecture,
    or the answer explicitly says it was not found."""
    _, arch = large_project_fixture
    arch_dict = arch.model_dump()
    architect = GemmaArchitect()
    all_class_names = {c.name for c in arch.classes}

    test_queries = [
        "What database entities and repositories are present?",
        "Explain the request flow for AuthController",
        "Does OrderController depend on OrderRepository?",
        "Who implements PaymentStrategy?",
        "List all endpoints in UserController",
        "Which database vendor is used?",
        "Is there an authentication component?",
        "Does NonExistentService connect to FakeRepo?",
        "Who depends on UserRepository?",
        "What are the declared methods of PaymentService?",
        "Explain the request flow for PaymentController",
        "Does ProductController depend on InventoryService?",
        "Show all controllers in the project",
        "Help me understand this codebase"
    ]

    ignored_tokens = {
        "String", "Long", "Integer", "Double", "Boolean", "List", "Set", "Map", "Optional",
        "Void", "Object", "Class", "Spring", "SpringBoot", "Controller", "Service", "Repository",
        "Entity", "DTO", "Java", "PostgreSQL", "MySQL", "H2", "Oracle", "MongoDB", "MariaDB",
        "REST", "HTTP", "JSON", "GET", "POST", "PUT", "DELETE", "PATCH", "JPA", "Hibernate",
        "Architecture", "Assistant", "Gemma", "Code2UML", "Table", "Id", "RequestMapping",
        "Based", "Evidence", "Files", "Types", "Classes", "Interfaces", "Endpoints", "Repositories",
        "Entities", "Controllers", "Services", "Packages", "Relationships", "Overview", "Project",
        "JpaRepository", "CrudRepository", "Large", "Enterprise", "Note", "Verification",
        "CreditCard", "Crypto", "Paypal", "Extends", "Manages", "Domain", "Implements",
        "Dependencies", "Declared", "Methods", "Fields", "Database", "Configuration", "Detected",
        "Libraries", "Filter", "Filters", "Security", "Components", "Delegates", "Downstream",
        "Calls", "Persist", "Query", "Found", "Handles", "Incoming", "Layer", "Base", "Path",
        "None", "Yes", "No", "However", "There", "Indirect", "Direct", "Directly", "Delegated",
        "Handling", "Processing"
    }

    for query in test_queries:
        ans = architect._deterministic_answer(query, arch_dict)
        # Extract backticked identifiers and candidate class tokens
        backtick_tokens = set(re.findall(r'`([A-Za-z0-9_]+)`', ans))
        for token in backtick_tokens:
            if not token or not token[0].isupper():
                continue
            if token in ignored_tokens:
                continue
            if token.endswith("s") and token[:-1] in all_class_names:
                continue
            if token.endswith("es") and token[:-2] in all_class_names:
                continue
            if any(token.startswith(p) for p in ["/", "GET", "POST", "PUT", "DELETE", "PATCH", "api"]):
                continue

            # Assert token is either in the architecture or the answer mentions it wasn't found
            exists_in_arch = token in all_class_names
            reported_missing = ("not found" in ans.lower() or "not determinable" in ans.lower() or "no authentication" in ans.lower() or "no such component" in ans.lower())
            assert exists_in_arch or reported_missing, f"Unverified class name '{token}' in answer to query '{query}':\n{ans}"

