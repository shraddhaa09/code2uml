import os
import tempfile
import pytest
from backend.analyzer.parser import JavaParser
from backend.analyzer.analyzer import ProjectAnalyzer


def test_sample_project_analyzer_golden_fixture():
    sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample-project")
    analyzer = ProjectAnalyzer(sample_dir, project_name="Sample Project")
    arch = analyzer.analyze()

    assert arch.project == "Sample Project"

    # 1. Type classification & counts
    assert arch.summary.total_types == 7
    assert arch.summary.total_classes == 7
    assert arch.summary.classes == 5
    assert arch.summary.interfaces == 2
    assert arch.summary.controllers == 1
    assert arch.summary.services == 1
    assert arch.summary.service_interfaces == 1
    assert arch.summary.repositories == 1
    assert arch.summary.entities == 1
    assert arch.summary.dtos == 1
    assert arch.summary.applications == 1
    assert arch.summary.endpoints == 4
    assert arch.summary.relationships == 10
    assert arch.summary.packages == 6

    # 2. Verify packages (6 distinct packages containing types)
    expected_packages = {
        "com.example.demo",
        "com.example.demo.controller",
        "com.example.demo.dto",
        "com.example.demo.model",
        "com.example.demo.repository",
        "com.example.demo.service"
    }
    assert set(arch.packages) == expected_packages

    # 3. Verify DemoApplication
    demo_app = next((c for c in arch.classes if c.name == "DemoApplication"), None)
    assert demo_app is not None
    assert demo_app.type == "application"
    assert not demo_app.is_interface
    assert "SpringBootApplication" in demo_app.annotations

    # 4. Verify UserController and its exact endpoints
    user_ctrl = next((c for c in arch.controllers if c.name == "UserController"), None)
    assert user_ctrl is not None
    assert user_ctrl.type == "controller"
    assert not user_ctrl.is_interface
    assert user_ctrl.base_path == "/api/users"
    assert "UserService" in user_ctrl.dependencies
    assert len(user_ctrl.endpoints) == 4

    endpoints_set = {(ep.http_method, ep.path) for ep in user_ctrl.endpoints}
    expected_endpoints = {
        ("GET", "/api/users"),
        ("GET", "/api/users/{id}"),
        ("POST", "/api/users"),
        ("DELETE", "/api/users/{id}")
    }
    assert endpoints_set == expected_endpoints

    # 5. Verify UserService (Service Interface) vs UserServiceImpl (Service)
    user_srv_iface = next((c for c in arch.service_interfaces if c.name == "UserService"), None)
    assert user_srv_iface is not None
    assert user_srv_iface.is_interface
    assert user_srv_iface.type == "service_interface"
    assert len(user_srv_iface.declared_methods) == 4
    assert any("getAllUsers" in m.name for m in user_srv_iface.declared_methods)

    user_srv_impl = next((c for c in arch.services if c.name == "UserServiceImpl"), None)
    assert user_srv_impl is not None
    assert not user_srv_impl.is_interface
    assert user_srv_impl.type == "service"
    assert "UserRepository" in user_srv_impl.dependencies
    assert "UserService" in user_srv_impl.implements

    # 6. Verify UserRepository
    user_repo = next((c for c in arch.repositories if c.name == "UserRepository"), None)
    assert user_repo is not None
    assert user_repo.is_interface
    assert user_repo.type == "repository"
    assert user_repo.extends == "JpaRepository<User, Long>"
    assert user_repo.managed_entity == "User"
    assert len(user_repo.declared_methods) == 1
    assert user_repo.declared_methods[0].name == "findByEmail"
    # Declared methods on repository must NOT be counted as REST endpoints
    assert len(user_repo.endpoints) == 0

    # 7. Verify User Entity
    user_entity = next((c for c in arch.entities if c.name == "User"), None)
    assert user_entity is not None
    assert not user_entity.is_interface
    assert user_entity.type == "entity"
    assert user_entity.table_name == "users"

    field_names = [f.name for f in user_entity.fields]
    assert "id" in field_names
    assert "name" in field_names
    assert "email" in field_names

    id_field = next((f for f in user_entity.fields if f.name == "id"), None)
    assert id_field is not None
    assert id_field.is_id
    assert "Id" in id_field.annotations
    assert "GeneratedValue" in id_field.annotations
    assert id_field.annotation_attributes.get("GeneratedValue", {}).get("strategy") == "GenerationType.IDENTITY"

    # 8. Verify UserDTO
    user_dto = next((c for c in arch.dtos if c.name == "UserDTO"), None)
    assert user_dto is not None
    assert not user_dto.is_interface
    assert user_dto.type == "dto"
    dto_field_names = [f.name for f in user_dto.fields]
    assert "name" in dto_field_names
    assert "email" in dto_field_names

    # 9. Verify Deduplicated Relationships (Exactly 10)
    assert len(arch.relationships) == 10

    # Strong relationships
    assert any(r.source == "UserController" and r.target == "UserService" and r.type == "dependency" for r in arch.relationships)
    assert any(r.source == "UserServiceImpl" and r.target == "UserRepository" and r.type == "dependency" for r in arch.relationships)
    assert any(r.source == "UserServiceImpl" and r.target == "UserService" and r.type == "implements" for r in arch.relationships)
    assert any(r.source == "UserRepository" and r.target == "User" and r.type == "manages_entity" for r in arch.relationships)

    # Ensure duplicate uses edge between UserRepository and User is suppressed
    assert not any(r.source == "UserRepository" and r.target == "User" and r.type in ["uses", "uses_entity"] for r in arch.relationships)

    # 10. Verify DemoApplication has zero outgoing relationships
    assert not any(r.source == "DemoApplication" for r in arch.relationships)

    # 11. Verify Architecture Observations (Deterministic Rules)
    assert len(arch.observations) >= 1
    assert any("UserController exposes the User entity directly in 3 endpoints" in o.message for o in arch.observations)
    assert any("consider returning UserDTO" in o.message for o in arch.observations)

    # No nodes or relationships to framework classes
    all_type_names = {c.name for c in arch.classes}
    for rel in arch.relationships:
        assert rel.source in all_type_names
        assert rel.target in all_type_names
        assert rel.source not in ["ResponseEntity", "Optional", "List", "JpaRepository"]
        assert rel.target not in ["ResponseEntity", "Optional", "List", "JpaRepository"]


def test_multi_package_and_complex_dependencies():
    with tempfile.TemporaryDirectory() as tmp_dir:
        p1 = os.path.join(tmp_dir, "com", "app", "order", "controller")
        os.makedirs(p1, exist_ok=True)
        with open(os.path.join(p1, "OrderController.java"), "w", encoding="utf-8") as f:
            f.write("""
            package com.app.order.controller;
            import org.springframework.web.bind.annotation.*;
            import com.app.order.service.OrderService;
            import com.app.payment.service.PaymentService;

            @RestController
            @RequestMapping("/api/orders")
            public class OrderController {
                private final OrderService orderService;
                private final PaymentService paymentService;

                public OrderController(OrderService orderService, PaymentService paymentService) {
                    this.orderService = orderService;
                    this.paymentService = paymentService;
                }

                @PostMapping("/checkout")
                public String checkout() { return "ok"; }
            }
            """)

        p2 = os.path.join(tmp_dir, "com", "app", "order", "service")
        os.makedirs(p2, exist_ok=True)
        with open(os.path.join(p2, "OrderService.java"), "w", encoding="utf-8") as f:
            f.write("""
            package com.app.order.service;
            import org.springframework.stereotype.Service;

            @Service
            public class OrderService {}
            """)

        p3 = os.path.join(tmp_dir, "com", "app", "payment", "service")
        os.makedirs(p3, exist_ok=True)
        with open(os.path.join(p3, "PaymentService.java"), "w", encoding="utf-8") as f:
            f.write("""
            package com.app.payment.service;
            import org.springframework.stereotype.Service;

            @Service
            public class PaymentService {}
            """)

        analyzer = ProjectAnalyzer(tmp_dir, project_name="MultiPackageApp")
        arch = analyzer.analyze()

        assert arch.summary.controllers == 1
        assert arch.summary.services == 2
        assert arch.summary.packages == 3

        ctrl = arch.controllers[0]
        assert "OrderService" in ctrl.dependencies
        assert "PaymentService" in ctrl.dependencies
        assert len(ctrl.endpoints) == 1
        assert ctrl.endpoints[0].path == "/api/orders/checkout"
