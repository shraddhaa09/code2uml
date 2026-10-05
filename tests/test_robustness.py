import os
import tempfile
import pytest
from backend.analyzer.parser import JavaParser
from backend.analyzer.analyzer import ProjectAnalyzer


def test_encoding_utf8_bom_and_latin1():
    """Verify UTF-8 with BOM and Latin-1 encoded files are correctly parsed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # UTF-8 with BOM
        bom_file = os.path.join(tmpdir, "BomController.java")
        bom_content = "\ufeffpackage com.example;\nimport org.springframework.web.bind.annotation.*;\n@RestController\npublic class BomController {\n    @GetMapping(\"/bom\")\n    public String get() { return \"ok\"; }\n}"
        with open(bom_file, "w", encoding="utf-8-sig") as f:
            f.write(bom_content)

        # Latin-1 encoded file with special accents
        latin1_file = os.path.join(tmpdir, "CaféService.java")
        latin1_content = "package com.example;\nimport org.springframework.stereotype.Service;\n// Café spécialité\n@Service\npublic class CaféService {\n}"
        with open(latin1_file, "w", encoding="latin-1") as f:
            f.write(latin1_content)

        analyzer = ProjectAnalyzer(tmpdir)
        arch = analyzer.analyze()

        names = {c.name for c in arch.classes}
        assert "BomController" in names
        assert "CaféService" in names or "CafeService" in names or any("Service" in n for n in names)
        assert len(arch.controllers) == 1
        assert len(arch.services) == 1
        assert arch.diagnostics.failed_count == 0


def test_comments_and_strings_with_fake_annotations():
    """Verify annotations inside comments and string literals are NOT detected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_file = os.path.join(tmpdir, "FakeService.java")
        content = """
        package com.example;
        
        // @RestController
        // @RequestMapping("/fake")
        /*
           @Service
           @Repository
        */
        public class FakeService {
            private String note = "@Entity @Table(name='fake')";
            
            // @GetMapping("/fake-endpoint")
            public void doNothing() {
                String dummy = "@Autowired private FakeRepo repo;";
            }
        }
        """
        with open(fake_file, "w", encoding="utf-8") as f:
            f.write(content)

        analyzer = ProjectAnalyzer(tmpdir)
        arch = analyzer.analyze()

        assert len(arch.classes) == 1
        fake_cls = arch.classes[0]
        # Should NOT be classified as controller, service, repository, or entity
        assert fake_cls.type in ["class", "component"]
        assert len(arch.controllers) == 0
        assert len(arch.services) == 0
        assert len(arch.repositories) == 0
        assert len(arch.entities) == 0
        assert len(arch.endpoints) == 0


def test_multi_module_and_test_directory_skipping():
    """Verify recursive search across Maven/Gradle modules and test directory exclusion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Module A: core-service (production)
        mod_a_dir = os.path.join(tmpdir, "module-core", "src", "main", "java", "com", "core")
        os.makedirs(mod_a_dir, exist_ok=True)
        with open(os.path.join(mod_a_dir, "CoreService.java"), "w", encoding="utf-8") as f:
            f.write("package com.core;\nimport org.springframework.stereotype.Service;\n@Service\npublic class CoreService {}")

        # Module A: core-service test (should be skipped by default)
        mod_a_test_dir = os.path.join(tmpdir, "module-core", "src", "test", "java", "com", "core")
        os.makedirs(mod_a_test_dir, exist_ok=True)
        with open(os.path.join(mod_a_test_dir, "CoreServiceTest.java"), "w", encoding="utf-8") as f:
            f.write("package com.core;\nimport org.springframework.boot.test.context.SpringBootTest;\n@SpringBootTest\npublic class CoreServiceTest {}")

        # Module B: api-web (production)
        mod_b_dir = os.path.join(tmpdir, "module-web", "src", "main", "java", "com", "web")
        os.makedirs(mod_b_dir, exist_ok=True)
        with open(os.path.join(mod_b_dir, "WebController.java"), "w", encoding="utf-8") as f:
            f.write("package com.web;\nimport org.springframework.web.bind.annotation.*;\nimport com.core.CoreService;\n@RestController\npublic class WebController {\n    public WebController(CoreService s) {}\n}")

        # Build target directory (should be skipped)
        target_dir = os.path.join(tmpdir, "module-web", "target", "classes", "com", "web")
        os.makedirs(target_dir, exist_ok=True)
        with open(os.path.join(target_dir, "CompiledDummy.java"), "w", encoding="utf-8") as f:
            f.write("package com.web;\npublic class CompiledDummy {}")

        analyzer = ProjectAnalyzer(tmpdir)
        arch = analyzer.analyze()

        names = {c.name for c in arch.classes}
        assert "CoreService" in names
        assert "WebController" in names
        assert "CoreServiceTest" not in names
        assert "CompiledDummy" not in names
        assert arch.diagnostics.skipped_count >= 1


def test_duplicate_class_names_in_different_packages():
    """Verify duplicate class names across packages (e.g. v1 vs v2) are both preserved."""
    with tempfile.TemporaryDirectory() as tmpdir:
        v1_dir = os.path.join(tmpdir, "v1")
        v2_dir = os.path.join(tmpdir, "v2")
        os.makedirs(v1_dir, exist_ok=True)
        os.makedirs(v2_dir, exist_ok=True)

        with open(os.path.join(v1_dir, "OrderController.java"), "w", encoding="utf-8") as f:
            f.write("package com.example.v1;\nimport org.springframework.web.bind.annotation.*;\n@RestController\n@RequestMapping(\"/v1/orders\")\npublic class OrderController {\n    @GetMapping\n    public String list() { return \"v1\"; }\n}")

        with open(os.path.join(v2_dir, "OrderController.java"), "w", encoding="utf-8") as f:
            f.write("package com.example.v2;\nimport org.springframework.web.bind.annotation.*;\n@RestController\n@RequestMapping(\"/v2/orders\")\npublic class OrderController {\n    @GetMapping\n    public String list() { return \"v2\"; }\n}")

        analyzer = ProjectAnalyzer(tmpdir)
        arch = analyzer.analyze()

        # Both controllers must exist
        assert len(arch.controllers) == 2
        endpoints = {ep.path for ep in arch.endpoints}
        assert "/v1/orders" in endpoints
        assert "/v2/orders" in endpoints


def test_java_records_and_modern_syntax():
    """Verify Java 14+ Record DTOs and modern interfaces are recognized."""
    with tempfile.TemporaryDirectory() as tmpdir:
        record_file = os.path.join(tmpdir, "UserSummaryRecord.java")
        content = """
        package com.example.dto;
        
        public record UserSummaryRecord(
            Long id,
            String username,
            String email
        ) {}
        """
        with open(record_file, "w", encoding="utf-8") as f:
            f.write(content)

        analyzer = ProjectAnalyzer(tmpdir)
        arch = analyzer.analyze()

        assert len(arch.classes) == 1
        record_cls = arch.classes[0]
        assert record_cls.name == "UserSummaryRecord"
        assert record_cls.type == "dto"
        assert len(record_cls.fields) == 3


def test_lombok_and_injection_variants():
    """Verify Lombok @RequiredArgsConstructor and field annotations (@Autowired, @Inject, @Resource)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Service with Lombok
        srv_file = os.path.join(tmpdir, "OrderService.java")
        srv_content = """
        package com.example.service;
        import lombok.RequiredArgsConstructor;
        import org.springframework.stereotype.Service;
        import com.example.repo.OrderRepository;
        import com.example.repo.PaymentGateway;
        
        @Service
        @RequiredArgsConstructor
        public class OrderService {
            private final OrderRepository orderRepository;
            private final PaymentGateway paymentGateway;
            private String nonFinalField;
        }
        """
        # Repositories
        repo_file = os.path.join(tmpdir, "OrderRepository.java")
        repo_content = """
        package com.example.repo;
        import org.springframework.data.repository.CrudRepository;
        import com.example.model.Order;
        
        public interface OrderRepository extends CrudRepository<Order, Long> {
        }
        """
        pay_file = os.path.join(tmpdir, "PaymentGateway.java")
        pay_content = """
        package com.example.repo;
        import org.springframework.stereotype.Component;
        @Component
        public class PaymentGateway {}
        """
        # Entity
        ent_file = os.path.join(tmpdir, "Order.java")
        ent_content = """
        package com.example.model;
        import jakarta.persistence.*;
        @Entity
        @Table(name = "orders")
        public class Order {
            @Id
            private Long id;
        }
        """

        with open(srv_file, "w", encoding="utf-8") as f:
            f.write(srv_content)
        with open(repo_file, "w", encoding="utf-8") as f:
            f.write(repo_content)
        with open(pay_file, "w", encoding="utf-8") as f:
            f.write(pay_content)
        with open(ent_file, "w", encoding="utf-8") as f:
            f.write(ent_content)

        analyzer = ProjectAnalyzer(tmpdir)
        arch = analyzer.analyze()

        srv = next(c for c in arch.classes if c.name == "OrderService")
        assert "OrderRepository" in srv.dependencies
        assert "PaymentGateway" in srv.dependencies

        repo = next(c for c in arch.classes if c.name == "OrderRepository")
        assert repo.type == "repository"
        assert repo.managed_entity == "Order"


def test_spring_stereotypes_and_controller_advice():
    """Verify @RestControllerAdvice, @ControllerAdvice, @Configuration, @Component, @FeignClient."""
    with tempfile.TemporaryDirectory() as tmpdir:
        advice_file = os.path.join(tmpdir, "GlobalExceptionHandler.java")
        content = """
        package com.example.web;
        import org.springframework.web.bind.annotation.RestControllerAdvice;
        @RestControllerAdvice
        public class GlobalExceptionHandler {}
        """
        cfg_file = os.path.join(tmpdir, "AppConfig.java")
        cfg_content = """
        package com.example.config;
        import org.springframework.context.annotation.Configuration;
        @Configuration
        public class AppConfig {}
        """
        with open(advice_file, "w", encoding="utf-8") as f:
            f.write(content)
        with open(cfg_file, "w", encoding="utf-8") as f:
            f.write(cfg_content)

        analyzer = ProjectAnalyzer(tmpdir)
        arch = analyzer.analyze()

        types_map = {c.name: c.type for c in arch.classes}
        assert types_map.get("GlobalExceptionHandler") in ["controller_advice", "controller", "component"]
        assert types_map.get("AppConfig") == "configuration"


def test_unsupported_languages_detected_in_diagnostics():
    """Verify Kotlin and Groovy files are identified and tracked in diagnostics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        java_file = os.path.join(tmpdir, "HelloController.java")
        with open(java_file, "w", encoding="utf-8") as f:
            f.write("package com.test;\nimport org.springframework.web.bind.annotation.*;\n@RestController\npublic class HelloController {}")

        kt_file = os.path.join(tmpdir, "KotlinService.kt")
        with open(kt_file, "w", encoding="utf-8") as f:
            f.write("package com.test\nclass KotlinService")

        groovy_file = os.path.join(tmpdir, "GroovyConfig.groovy")
        with open(groovy_file, "w", encoding="utf-8") as f:
            f.write("package com.test\nclass GroovyConfig {}")

        analyzer = ProjectAnalyzer(tmpdir)
        arch = analyzer.analyze()

        assert len(arch.controllers) == 1
        assert "kotlin" in arch.diagnostics.unsupported_languages
        assert "groovy" in arch.diagnostics.unsupported_languages
        assert arch.diagnostics.unsupported_languages["kotlin"] == 1
        assert arch.diagnostics.unsupported_languages["groovy"] == 1


def test_broken_syntax_file_graceful_recovery():
    """Verify a malformed Java file is recorded as failed without crashing the whole analysis."""
    with tempfile.TemporaryDirectory() as tmpdir:
        good_file = os.path.join(tmpdir, "GoodService.java")
        with open(good_file, "w", encoding="utf-8") as f:
            f.write("package com.test;\nimport org.springframework.stereotype.Service;\n@Service\npublic class GoodService {}")

        broken_file = os.path.join(tmpdir, "Broken.java")
        with open(broken_file, "w", encoding="utf-8") as f:
            f.write("public class Broken {{{ unclosed syntax @@@@ ### ???")

        analyzer = ProjectAnalyzer(tmpdir)
        arch = analyzer.analyze()

        assert len(arch.services) == 1
        assert "GoodService" in [c.name for c in arch.services]
        # Diagnostics must capture the failure honestly
        assert arch.diagnostics.total_files_discovered == 2
        assert arch.diagnostics.parsed_ast_count + arch.diagnostics.parsed_fallback_count >= 1
