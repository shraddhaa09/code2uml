import os
import random
import string
import tempfile
import time
import pytest
from backend.analyzer.analyzer import ProjectAnalyzer


def test_fuzz_corrupted_java_sources():
    """
    Take valid Java files, apply random corruptions (truncation, binary noise,
    unmatched braces, random fake annotations in comments/strings),
    and assert the analyzer NEVER raises an unhandled exception and always returns diagnostics.
    """
    random.seed(42)
    sample_templates = [
        """package com.example.fuzz;
import org.springframework.web.bind.annotation.*;
@RestController
@RequestMapping("/api/fuzz")
public class FuzzController {
    @GetMapping("/{id}")
    public String get(@PathVariable String id) { return id; }
}
""",
        """package com.example.fuzz;
import org.springframework.stereotype.Service;
@Service
public class FuzzService {
    public void execute() {}
}
""",
        """package com.example.fuzz;
import jakarta.persistence.*;
@Entity
public class FuzzEntity {
    @Id
    private Long id;
}
"""
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        # Generate 20 corrupted files
        for i in range(20):
            template = random.choice(sample_templates)
            corruption_type = random.choice(["truncate", "binary_inject", "broken_braces", "fake_annos", "null_bytes"])
            
            if corruption_type == "truncate":
                corrupted = template[:len(template) // 2]
            elif corruption_type == "binary_inject":
                corrupted = template[:20] + "\x00\xff\xfe\x01\x02\x03" + template[20:]
            elif corruption_type == "broken_braces":
                corrupted = template.replace("{", "{{{{").replace("}", "")
            elif corruption_type == "fake_annos":
                corrupted = template + "\n// @RestController @Service\nString s = \"@Repository @Entity\";\n"
            else:
                corrupted = template.replace("public", "\x00public\x00")

            file_path = os.path.join(tmpdir, f"FuzzClass_{i}.java")
            with open(file_path, "wb") as f:
                f.write(corrupted.encode("utf-8", errors="ignore"))

        # Analyze corrupted directory - must NEVER crash
        analyzer = ProjectAnalyzer(tmpdir)
        arch = analyzer.analyze()

        assert arch is not None
        assert arch.diagnostics.total_files_discovered == 20
        assert arch.diagnostics.coverage_percentage >= 0.0


def test_performance_200_files_benchmark():
    """
    Generate a 200-class Spring Boot project layout and measure deterministic parse/analysis time.
    Asserts throughput is fast (e.g. < 3 seconds for 200 files).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Generate 200 diverse Spring Boot classes across 5 packages
        packages = ["controller", "service", "repository", "model", "dto"]
        for p in packages:
            os.makedirs(os.path.join(tmpdir, p), exist_ok=True)

        for i in range(40):
            # Controller
            with open(os.path.join(tmpdir, "controller", f"Item{i}Controller.java"), "w", encoding="utf-8") as f:
                f.write(f"""package com.example.controller;
import org.springframework.web.bind.annotation.*;
import com.example.service.Item{i}Service;
@RestController
@RequestMapping("/api/items{i}")
public class Item{i}Controller {{
    private final Item{i}Service service;
    public Item{i}Controller(Item{i}Service service) {{ this.service = service; }}
    @GetMapping
    public String get() {{ return "ok"; }}
}}
""")

            # Service
            with open(os.path.join(tmpdir, "service", f"Item{i}Service.java"), "w", encoding="utf-8") as f:
                f.write(f"""package com.example.service;
import org.springframework.stereotype.Service;
import com.example.repository.Item{i}Repository;
@Service
public class Item{i}Service {{
    private final Item{i}Repository repository;
    public Item{i}Service(Item{i}Repository repository) {{ this.repository = repository; }}
}}
""")

            # Repository
            with open(os.path.join(tmpdir, "repository", f"Item{i}Repository.java"), "w", encoding="utf-8") as f:
                f.write(f"""package com.example.repository;
import org.springframework.data.jpa.repository.JpaRepository;
import com.example.model.Item{i};
public interface Item{i}Repository extends JpaRepository<Item{i}, Long> {{
}}
""")

            # Model
            with open(os.path.join(tmpdir, "model", f"Item{i}.java"), "w", encoding="utf-8") as f:
                f.write(f"""package com.example.model;
import jakarta.persistence.*;
@Entity
public class Item{i} {{
    @Id
    private Long id;
}}
""")

            # DTO
            with open(os.path.join(tmpdir, "dto", f"Item{i}DTO.java"), "w", encoding="utf-8") as f:
                f.write(f"""package com.example.dto;
public class Item{i}DTO {{
    private String name;
}}
""")

        # Measure analysis time
        start_time = time.perf_counter()
        analyzer = ProjectAnalyzer(tmpdir)
        arch = analyzer.analyze()
        duration = time.perf_counter() - start_time

        assert len(arch.classes) == 200
        assert len(arch.controllers) == 40
        assert len(arch.services) == 40
        assert len(arch.repositories) == 40
        assert len(arch.entities) == 40
        assert len(arch.dtos) == 40
        assert arch.diagnostics.total_files_discovered == 200
        assert arch.diagnostics.coverage_percentage == 100.0

        # Assert performance constraint: 200 files parsed and mapped in under 5.0 seconds
        print(f"\n[BENCHMARK] Analyzed 200 Spring Boot files in {duration:.3f}s ({200/duration:.1f} files/sec)")
        assert duration < 5.0
