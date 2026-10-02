import os
import pytest
from backend.analyzer.analyzer import ProjectAnalyzer
from backend.diagram.mermaid import MermaidGenerator, sanitize_id, sanitize_label, escape_uml_generics
from backend.analyzer.models import Architecture, ArchitectureSummary, ClassInfo


def test_mermaid_generation():
    sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample-project")
    analyzer = ProjectAnalyzer(sample_dir, project_name="Sample Project")
    arch = analyzer.analyze()
    
    # 1. Default mode (flowchart TD)
    mermaid_default = MermaidGenerator.generate(arch, mode="default")
    assert mermaid_default.startswith("flowchart TD")
    assert "subgraph ControllersLayer" in mermaid_default
    assert "subgraph ServicesLayer" in mermaid_default
    assert "subgraph RepositoriesLayer" in mermaid_default
    assert "subgraph EntitiesLayer" in mermaid_default
    assert "subgraph ApplicationLayer [🔧 Application Entry Point]" in mermaid_default
    assert "&laquo;SpringBootApplication&raquo;" in mermaid_default
    assert "UserController --> UserService" in mermaid_default
    assert "UserServiceImpl --> UserRepository" in mermaid_default
    assert "UserServiceImpl -.->|implements| UserService" in mermaid_default
    
    # Relabeled edge: UserRepository ==>|depends| User
    assert "UserRepository ==>|depends| User" in mermaid_default
    assert "extends JpaRepository&lt;User, Long&gt;" in mermaid_default
    
    # No JpaRepository node
    assert "JpaRepository[" not in mermaid_default

    # DemoApplication has no outgoing edges
    for line in mermaid_default.splitlines():
        if "-->" in line or "-.->" in line or "==>" in line or "--|>" in line:
            assert not line.strip().startswith("DemoApplication ")

    # All 4 endpoints of UserController must be rendered without +more truncation
    assert "GET</b> /api/users" in mermaid_default
    assert "GET</b> /api/users/{id}" in mermaid_default
    assert "POST</b> /api/users" in mermaid_default
    assert "DELETE</b> /api/users/{id}" in mermaid_default
    assert "+1 more" not in mermaid_default

    # 2. Full mode
    mermaid_full = MermaidGenerator.generate(arch, mode="full")
    assert "UserController -.->|uses| User" in mermaid_full
    assert "UserService -.->|uses| User" in mermaid_full
    assert "UserServiceImpl -.->|uses| User" in mermaid_full


def test_mermaid_uml_class_diagram_generation():
    sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample-project")
    analyzer = ProjectAnalyzer(sample_dir, project_name="Sample Project")
    arch = analyzer.analyze()

    uml_code = MermaidGenerator.generate_uml(arch)
    assert uml_code.startswith("classDiagram")

    # Classes and stereotypes
    assert "class UserController {" in uml_code
    assert "<<RestController>>" in uml_code
    assert "class UserService {" in uml_code
    assert "<<interface>>" in uml_code
    assert "class UserServiceImpl {" in uml_code
    assert "<<Service>>" in uml_code
    assert "class UserRepository {" in uml_code
    assert "<<Repository>>" in uml_code
    assert "class User {" in uml_code
    assert "<<Entity>>" in uml_code
    assert "class UserDTO {" in uml_code
    assert "<<DTO>>" in uml_code
    assert "class DemoApplication {" in uml_code
    assert "<<SpringBootApplication>>" in uml_code

    # Generic escaping: uses ~ instead of < >
    assert "List~User~" in uml_code
    assert "Optional~User~" in uml_code
    assert 'note for UserRepository "extends JpaRepository~User, Long~"' in uml_code

    # UML Relationships
    assert "UserServiceImpl ..|> UserService : implements" in uml_code
    assert "UserRepository --> User : depends" in uml_code
    assert "UserController --> UserService : uses" in uml_code
    assert "UserServiceImpl --> UserRepository : uses" in uml_code
    assert "UserController ..> UserDTO : uses" in uml_code
    assert "UserController ..> User : uses" in uml_code
    assert "UserServiceImpl ..> UserDTO : uses" in uml_code
    assert "UserServiceImpl ..> User : uses" in uml_code
    assert "UserService ..> UserDTO : uses" in uml_code
    assert "UserService ..> User : uses" in uml_code

    # DemoApplication has zero outgoing relationships
    for line in uml_code.splitlines():
        if "-->" in line or "..|>" in line or "..>" in line or "--|>" in line:
            assert not line.strip().startswith("DemoApplication ")

    # No JpaRepository class node
    assert "class JpaRepository {" not in uml_code


def test_mermaid_empty_and_special_chars():
    empty_arch = Architecture(
        project="Empty",
        summary=ArchitectureSummary(),
        classes=[],
        controllers=[],
        services=[],
        repositories=[],
        entities=[],
        relationships=[],
        endpoints=[]
    )
    code = MermaidGenerator.generate(empty_arch)
    assert "EmptyProject" in code

    uml = MermaidGenerator.generate_uml(empty_arch)
    assert "EmptyProject" in uml

    # Test sanitizers
    assert sanitize_id("My-Class<Name>") == "My_Class_Name_"
    assert sanitize_label('class <User> "test"') == 'class &lt;User&gt; &quot;test&quot;'
    assert escape_uml_generics("JpaRepository<User, Long>") == "JpaRepository~User, Long~"
