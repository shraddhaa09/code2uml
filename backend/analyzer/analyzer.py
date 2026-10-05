import os
import re
import uuid
from typing import List, Dict, Set, Optional, Tuple, Any
from backend.analyzer.models import (
    ClassInfo,
    FieldInfo,
    MethodInfo,
    MethodParamInfo,
    EndpointInfo,
    RelationshipInfo,
    ArchitectureSummary,
    Observation,
    FileParseDiagnostic,
    AnalysisDiagnostics,
    Architecture
)
from backend.analyzer.parser import JavaParser, JavaParsedFile


def extract_base_type(type_str: str) -> str:
    """Strip generics like List<User> -> User or JpaRepository<User, Long> -> User"""
    if not type_str:
        return ""
    m = re.search(r'<([A-Za-z0-9_,\s]+)>', type_str)
    if m:
        first_arg = m.group(1).split(",")[0].strip()
        if first_arg:
            return first_arg
    return type_str.strip()


def extract_all_generic_args(type_str: str) -> List[str]:
    """Extract all generic arguments: JpaRepository<User, Long> -> ['User', 'Long']"""
    if not type_str:
        return []
    m = re.search(r'<([A-Za-z0-9_,\s]+)>', type_str)
    if m:
        return [arg.strip() for arg in m.group(1).split(",") if arg.strip()]
    return []


# Standard directories to skip during scanning
DEFAULT_SKIPPED_DIRS = {
    ".git", "target", "build", ".gradle", "bin", ".idea", "node_modules",
    "__MACOSX", ".mvn", "out", ".settings", ".vscode"
}

# Supported repositories base names
REPO_PARENT_NAMES = {
    "Repository", "JpaRepository", "CrudRepository", "PagingAndSortingRepository",
    "MongoRepository", "ReactiveCrudRepository", "ReactiveMongoRepository", "R2dbcRepository"
}


class ProjectAnalyzer:
    """
    Deterministic Java & Spring Boot static architecture analyzer with
    resilient multi-module scanning, diagnostics, and injection resolution.
    """

    def __init__(self, root_dir: str, project_name: Optional[str] = None, include_tests: bool = False):
        self.root_dir = os.path.abspath(root_dir)
        self.project_name = project_name or os.path.basename(self.root_dir)
        self.include_tests = include_tests

    def analyze(self) -> Architecture:
        # Step 1: Scan and discover files with bounds checking
        java_files: List[str] = []
        unsupported_files: Dict[str, int] = {}
        skipped_files_count = 0
        file_diagnostics: List[FileParseDiagnostic] = []
        warnings: List[str] = []

        MAX_FILES = 1000
        MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB cap per file

        for root, dirs, files in os.walk(self.root_dir):
            # Prune skipped directories
            dirs[:] = [
                d for d in dirs
                if d not in DEFAULT_SKIPPED_DIRS and not d.startswith(".")
            ]

            # Check if current path is a test directory (e.g. src/test/java or test/)
            rel_root = os.path.relpath(root, self.root_dir).replace("\\", "/")
            is_test_dir = False
            if not self.include_tests:
                norm_root = "/" + rel_root.strip("/") + "/"
                if "/src/test/" in norm_root or norm_root.startswith("/test/") or norm_root.startswith("/tests/") or norm_root in ["/test/", "/tests/"]:
                    is_test_dir = True

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                full_path = os.path.join(root, file)
                rel_fpath = os.path.relpath(full_path, self.root_dir).replace("\\", "/")

                if is_test_dir:
                    if ext == ".java":
                        skipped_files_count += 1
                    continue

                if ext == ".java":
                    if len(java_files) >= MAX_FILES:
                        warnings.append(f"Maximum file limit of {MAX_FILES} reached. Remaining files were omitted.")
                        break

                    try:
                        fsize = os.path.getsize(full_path)
                        if fsize > MAX_FILE_SIZE:
                            warnings.append(f"File {rel_fpath} exceeds size limit of {MAX_FILE_SIZE//(1024*1024)}MB and was skipped.")
                            skipped_files_count += 1
                            continue
                    except OSError:
                        pass

                    java_files.append(full_path)

                elif ext in [".kt", ".kts"]:
                    unsupported_files["kotlin"] = unsupported_files.get("kotlin", 0) + 1
                elif ext in [".groovy", ".gvy"]:
                    unsupported_files["groovy"] = unsupported_files.get("groovy", 0) + 1
                elif ext == ".scala":
                    unsupported_files["scala"] = unsupported_files.get("scala", 0) + 1

        # Step 2: Parse all discovered Java files
        parsed_files: List[JavaParsedFile] = []
        parsed_ast_count = 0
        parsed_fallback_count = 0
        failed_count = 0

        for jfile in java_files:
            rel_path = os.path.relpath(jfile, self.root_dir).replace("\\", "/")
            parsed = JavaParser.parse_file(jfile, rel_path)
            parsed_files.append(parsed)

            if parsed.parse_method == "ast":
                parsed_ast_count += 1
            elif parsed.parse_method == "fallback":
                parsed_fallback_count += 1
            else:
                failed_count += 1

            file_diagnostics.append(FileParseDiagnostic(
                file=rel_path,
                method=parsed.parse_method,
                types_count=len(parsed.types),
                error=parsed.error_message
            ))

        # Step 3: Index discovered types by Fully Qualified Name (FQN)
        discovered_by_fqn: Dict[str, Dict] = {}
        simple_to_fqns: Dict[str, List[str]] = {}
        distinct_packages: Set[str] = set()

        for pfile in parsed_files:
            if pfile.package:
                distinct_packages.add(pfile.package)
            for t in pfile.types:
                t_name = t["name"]
                fqn = f"{pfile.package}.{t_name}" if pfile.package else t_name
                discovered_by_fqn[fqn] = {
                    "raw": t,
                    "name": t_name,
                    "fqn": fqn,
                    "package": pfile.package,
                    "file": pfile.relative_path,
                    "imports": pfile.imports
                }
                simple_to_fqns.setdefault(t_name, []).append(fqn)

        # Helper to resolve type reference to FQN
        def resolve_type_fqn(type_name: str, current_pkg: str, current_imports: List[str]) -> Optional[str]:
            if not type_name:
                return None
            clean_name = extract_base_type(type_name)
            # 1. Exact FQN match
            if clean_name in discovered_by_fqn:
                return clean_name
            # 2. Check explicit imports
            for imp in current_imports:
                if imp.endswith(f".{clean_name}"):
                    if imp in discovered_by_fqn:
                        return imp
            # 3. Check same package
            same_pkg_fqn = f"{current_pkg}.{clean_name}" if current_pkg else clean_name
            if same_pkg_fqn in discovered_by_fqn:
                return same_pkg_fqn
            # 4. Check unique simple name across whole project
            candidate_fqns = simple_to_fqns.get(clean_name, [])
            if len(candidate_fqns) == 1:
                return candidate_fqns[0]
            return None

        # Step 4: Classify types and extract rich metadata
        classes_map: Dict[str, ClassInfo] = {}
        controllers: List[ClassInfo] = []
        services: List[ClassInfo] = []
        service_interfaces: List[ClassInfo] = []
        repositories: List[ClassInfo] = []
        entities: List[ClassInfo] = []
        dtos: List[ClassInfo] = []
        applications: List[ClassInfo] = []
        all_endpoints: List[EndpointInfo] = []

        for fqn, data in discovered_by_fqn.items():
            raw = data["raw"]
            name = data["name"]
            pkg = data["package"]
            file_rel = data["file"]
            annos = raw.get("annotations", [])
            anno_attrs = raw.get("annotation_attributes", {})
            anno_set = set(annos)
            is_interface = bool(raw.get("is_interface", False))
            is_record = bool(raw.get("is_record", False))

            # Table name for entities
            table_name = None
            if "Table" in anno_attrs and ("name" in anno_attrs["Table"] or "value" in anno_attrs["Table"]):
                table_name = anno_attrs["Table"].get("name") or anno_attrs["Table"].get("value")

            # Base path for controllers
            base_path = None
            if "RequestMapping" in anno_attrs and ("value" in anno_attrs["RequestMapping"] or "path" in anno_attrs["RequestMapping"]):
                base_path = anno_attrs["RequestMapping"].get("value") or anno_attrs["RequestMapping"].get("path")

            # Managed entity for repositories
            managed_entity = None
            if raw.get("extends"):
                raw_ext = raw["extends"]
                if any(r_p in raw_ext for r_p in REPO_PARENT_NAMES):
                    gen_args = extract_all_generic_args(raw_ext)
                    if gen_args:
                        managed_entity = gen_args[0]

            # Determine type & heuristic
            ctype = "class"
            heuristic = None
            if "SpringBootApplication" in anno_set:
                ctype = "application"
            elif "RestController" in anno_set or "Controller" in anno_set or "RestControllerAdvice" in anno_set or "ControllerAdvice" in anno_set:
                ctype = "controller"
            elif "Service" in anno_set and not is_interface:
                ctype = "service"
            elif is_interface and (
                "Repository" in anno_set
                or any(r_p in (raw.get("extends") or "") for r_p in REPO_PARENT_NAMES)
            ):
                ctype = "repository"
            elif is_interface and ("service" in pkg.lower() or name.endswith("Service")):
                ctype = "service_interface"
            elif is_interface:
                ctype = "interface"
            elif "Repository" in anno_set or any(r_p in (raw.get("extends") or "") for r_p in REPO_PARENT_NAMES):
                ctype = "repository"
            elif "Entity" in anno_set or "Table" in anno_set or "Document" in anno_set or "MappedSuperclass" in anno_set or "Embeddable" in anno_set:
                ctype = "entity"
            elif "Configuration" in anno_set:
                ctype = "configuration"
            elif "Component" in anno_set or "FeignClient" in anno_set or "Mapper" in anno_set:
                ctype = "component"
            elif is_record:
                ctype = "dto"
                heuristic = "Java record declaration"
            elif name.endswith(("DTO", "Dto", "Request", "Response", "Payload", "Command", "Query", "VO")):
                ctype = "dto"
                heuristic = "Name pattern (*Dto/*Request/*Response)"
            elif "dto" in pkg.lower():
                ctype = "dto"
                heuristic = "Package name ('dto')"

            # Parse fields
            field_infos: List[FieldInfo] = []
            for f in raw.get("fields", []):
                field_infos.append(FieldInfo(
                    name=f["name"],
                    type=f["type"],
                    annotations=f.get("annotations", []),
                    annotation_attributes=f.get("annotation_attributes", {}),
                    is_id=f.get("is_id", False)
                ))

            # Parse declared methods
            method_infos: List[MethodInfo] = []
            for m in raw.get("declared_methods", []):
                params_list = [MethodParamInfo(name=p["name"], type=p["type"]) for p in m.get("parameters", [])]
                method_infos.append(MethodInfo(
                    name=m["name"],
                    return_type=m.get("return_type", "void"),
                    parameters=params_list,
                    signature=m.get("signature", f"{m['name']}()"),
                    annotations=m.get("annotations", []),
                    annotation_attributes=m.get("annotation_attributes", {})
                ))

            # Endpoints (ONLY for controllers)
            endpoint_infos: List[EndpointInfo] = []
            if ctype == "controller":
                for ep in raw.get("endpoints", []):
                    ep_obj = EndpointInfo(
                        http_method=ep["http_method"],
                        path=ep["path"],
                        method_name=ep["method_name"],
                        return_type=ep.get("return_type"),
                        controller=name
                    )
                    endpoint_infos.append(ep_obj)
                    all_endpoints.append(ep_obj)

            class_info = ClassInfo(
                name=name,
                package=pkg,
                type=ctype,
                is_interface=is_interface,
                annotations=annos,
                annotation_attributes=anno_attrs,
                dependencies=[],
                implements=raw.get("implements", []),
                extends=raw.get("extends"),
                file=file_rel,
                endpoints=endpoint_infos,
                methods=raw.get("methods", []),
                declared_methods=method_infos,
                fields=field_infos,
                base_path=base_path,
                table_name=table_name,
                managed_entity=managed_entity,
                detection_heuristic=heuristic
            )
            classes_map[fqn] = class_info

        # Step 5: Detect relationships & injection flows
        candidate_rels: List[RelationshipInfo] = []

        def add_candidate(source_name: str, target_name: str, rel_type: str, desc: Optional[str] = None):
            if source_name != target_name and target_name in simple_to_fqns:
                candidate_rels.append(RelationshipInfo(
                    source=source_name,
                    target=target_name,
                    type=rel_type,
                    description=desc
                ))

        for fqn, data in discovered_by_fqn.items():
            raw = data["raw"]
            name = data["name"]
            pkg = data["package"]
            imports = data["imports"]
            cinfo = classes_map[fqn]
            deps: Set[str] = set()
            annos = set(raw.get("annotations", []))

            # Has Lombok constructor injection?
            has_lombok_req_ctor = ("RequiredArgsConstructor" in annos or "Data" in annos or "Value" in annos)
            has_lombok_all_ctor = ("AllArgsConstructor" in annos)

            # 1. Constructor dependencies
            for ctor in raw.get("constructors", []):
                for param in ctor.get("parameters", []):
                    target_fqn = resolve_type_fqn(param.get("type", ""), pkg, imports)
                    if target_fqn and target_fqn != fqn:
                        target_name = discovered_by_fqn[target_fqn]["name"]
                        deps.add(target_name)
                        add_candidate(name, target_name, "dependency", "injected via constructor")

            # 2. Field dependencies (explicit injection or Lombok)
            for f in raw.get("fields", []):
                ftype = f.get("type", "")
                fannos = set(f.get("annotations", []))
                is_final = f.get("is_final", False)
                is_injected = (
                    "Autowired" in fannos or "Inject" in fannos or "Resource" in fannos
                    or (has_lombok_req_ctor and is_final)
                    or has_lombok_all_ctor
                )
                target_fqn = resolve_type_fqn(ftype, pkg, imports)
                if target_fqn and target_fqn != fqn:
                    target_name = discovered_by_fqn[target_fqn]["name"]
                    if is_injected:
                        deps.add(target_name)
                        add_candidate(name, target_name, "dependency", "injected via field")
                    else:
                        add_candidate(name, target_name, "uses", "references field")

            # 3. Setter injection (@Autowired on setter methods)
            for m in raw.get("declared_methods", []):
                m_annos = set(m.get("annotations", []))
                if "Autowired" in m_annos or "Inject" in m_annos or "Resource" in m_annos:
                    for p in m.get("parameters", []):
                        target_fqn = resolve_type_fqn(p.get("type", ""), pkg, imports)
                        if target_fqn and target_fqn != fqn:
                            target_name = discovered_by_fqn[target_fqn]["name"]
                            deps.add(target_name)
                            add_candidate(name, target_name, "dependency", "injected via setter")

            # 4. Implements interface relationships
            for imp in raw.get("implements", []):
                target_fqn = resolve_type_fqn(imp, pkg, imports)
                if target_fqn and target_fqn != fqn:
                    target_name = discovered_by_fqn[target_fqn]["name"]
                    add_candidate(name, target_name, "implements", f"implements {target_name}")

            # 5. Extends relationships
            if raw.get("extends"):
                raw_extends = raw["extends"]
                base_ext_name = raw_extends.split("<")[0].strip()
                target_fqn = resolve_type_fqn(base_ext_name, pkg, imports)
                if target_fqn and target_fqn != fqn:
                    target_name = discovered_by_fqn[target_fqn]["name"]
                    add_candidate(name, target_name, "extends", f"extends {target_name}")

                # Check if repository manages entity via generic argument
                if any(r_p in raw_extends for r_p in REPO_PARENT_NAMES):
                    generic_args = extract_all_generic_args(raw_extends)
                    for g_arg in generic_args:
                        g_fqn = resolve_type_fqn(g_arg, pkg, imports)
                        if g_fqn and classes_map.get(g_fqn) and classes_map[g_fqn].type == "entity":
                            target_name = discovered_by_fqn[g_fqn]["name"]
                            deps.add(target_name)
                            add_candidate(name, target_name, "manages_entity", f"repository manages {target_name}")

            # 6. Method parameter/return type DTO/Entity usages
            for m in raw.get("declared_methods", []):
                m_ret = extract_base_type(m.get("return_type", ""))
                target_fqn = resolve_type_fqn(m_ret, pkg, imports)
                if target_fqn and target_fqn != fqn:
                    target_info = classes_map.get(target_fqn)
                    if target_info and target_info.type in ["dto", "entity"]:
                        target_name = target_info.name
                        rel_t = "uses_dto" if target_info.type == "dto" else "uses_entity"
                        add_candidate(name, target_name, rel_t, f"method {m['name']} returns {target_name}")

                for p in m.get("parameters", []):
                    ptype = extract_base_type(p.get("type", ""))
                    target_fqn = resolve_type_fqn(ptype, pkg, imports)
                    if target_fqn and target_fqn != fqn:
                        target_info = classes_map.get(target_fqn)
                        if target_info and target_info.type in ["dto", "entity"]:
                            target_name = target_info.name
                            rel_t = "uses_dto" if target_info.type == "dto" else "uses_entity"
                            add_candidate(name, target_name, rel_t, f"method {m['name']} accepts {target_name}")

            cinfo.dependencies = sorted(list(deps))

            # Categorize into lists
            if cinfo.type == "controller":
                controllers.append(cinfo)
            elif cinfo.type == "service":
                services.append(cinfo)
            elif cinfo.type == "service_interface":
                service_interfaces.append(cinfo)
            elif cinfo.type == "repository":
                repositories.append(cinfo)
            elif cinfo.type == "entity":
                entities.append(cinfo)
            elif cinfo.type == "dto":
                dtos.append(cinfo)
            elif cinfo.type == "application":
                applications.append(cinfo)

        # Step 6: Deduplicate and filter relationships
        STRONG_REL_TYPES = {"dependency", "implements", "extends", "manages_entity", "manages", "injects"}
        GENERIC_USES_TYPES = {"uses", "uses_dto", "uses_entity"}

        pair_has_strong: Set[Tuple[str, str]] = set()
        for r in candidate_rels:
            if r.type in STRONG_REL_TYPES:
                pair_has_strong.add((r.source, r.target))

        final_relationships: List[RelationshipInfo] = []
        seen_rel_signatures: Set[str] = set()

        for r in candidate_rels:
            if (r.source, r.target) in pair_has_strong and r.type in GENERIC_USES_TYPES:
                continue

            sig = f"{r.source}->{r.target}:{r.type}"
            if sig not in seen_rel_signatures:
                seen_rel_signatures.add(sig)
                final_relationships.append(r)

        # Step 7: Architecture Observations (Deterministic Rules)
        all_classes_list = list(classes_map.values())
        observations: List[Observation] = []
        entity_names = {e.name for e in entities}
        dto_names = {d.name for d in dtos}
        dto_suggestion = next(iter(dto_names), "a DTO")

        # Observation 1: Direct entity exposure in controller endpoints
        for ctrl in controllers:
            entity_endpoint_counts: Dict[str, int] = {}
            for ep in ctrl.endpoints:
                ret_base = extract_base_type(ep.return_type or "")
                if ret_base in entity_names:
                    entity_endpoint_counts[ret_base] = entity_endpoint_counts.get(ret_base, 0) + 1

            for ent_name, count in entity_endpoint_counts.items():
                matching_dto = next((d for d in dto_names if ent_name in d or d in ent_name), dto_suggestion)
                observations.append(Observation(
                    severity="warning",
                    message=f"{ctrl.name} exposes the {ent_name} entity directly in {count} endpoints; consider returning {matching_dto}.",
                    components=[ctrl.name, ent_name]
                ))

        # Observation 2: Layer skip (Controller directly injecting a Repository)
        repo_names = {r.name for r in repositories}
        for ctrl in controllers:
            for dep in ctrl.dependencies:
                if dep in repo_names:
                    observations.append(Observation(
                        severity="warning",
                        message=f"{ctrl.name} directly injects repository {dep} (layer skip); consider routing through a service.",
                        components=[ctrl.name, dep]
                    ))

        # Observation 3: Service interface with no implementation
        all_implemented_ifaces: Set[str] = set()
        for c in all_classes_list:
            for imp in c.implements:
                all_implemented_ifaces.add(imp)
                all_implemented_ifaces.add(imp.split("<")[0].strip())
                if "." in imp:
                    all_implemented_ifaces.add(imp.split(".")[-1])
            if c.name.endswith("Impl"):
                all_implemented_ifaces.add(c.name[:-4])

        for si in service_interfaces:
            if si.name not in all_implemented_ifaces:
                observations.append(Observation(
                    severity="info",
                    message=f"Service interface {si.name} has no implementing class detected in the codebase.",
                    components=[si.name]
                ))

        # Check for non-Spring project warning
        if len(controllers) == 0 and len(services) == 0 and len(repositories) == 0 and len(applications) == 0:
            warnings.append("No Spring Boot components detected; this may not be a Spring Boot project (0 controllers, 0 services, 0 repositories, 0 applications detected).")

        # Detect database vendor & authentication configuration
        database_info = self._detect_database_vendor()
        auth_info = self._detect_authentication(classes_map)

        # Step 8: Calculate Diagnostics & Summary
        total_discovered = len(java_files)
        total_parsed = parsed_ast_count + parsed_fallback_count
        coverage = round((total_parsed / total_discovered * 100.0), 1) if total_discovered > 0 else 100.0

        diagnostics = AnalysisDiagnostics(
            total_files_discovered=total_discovered,
            parsed_ast_count=parsed_ast_count,
            parsed_fallback_count=parsed_fallback_count,
            failed_count=failed_count,
            skipped_count=skipped_files_count,
            unsupported_languages=unsupported_files,
            coverage_percentage=coverage,
            warnings=warnings,
            file_details=file_diagnostics
        )

        all_classes_list = list(classes_map.values())
        class_count = sum(1 for c in all_classes_list if not c.is_interface)
        interface_count = sum(1 for c in all_classes_list if c.is_interface)

        # Package counting fix: ensure default package is accounted for
        has_default_package = any(not c.package for c in all_classes_list)
        packages_set = set(distinct_packages)
        if has_default_package or not packages_set:
            packages_set.add("(default)")
        packages_list = sorted(list(packages_set))

        summary = ArchitectureSummary(
            total_types=len(all_classes_list),
            total_classes=len(all_classes_list),
            classes=class_count,
            interfaces=interface_count,
            controllers=len(controllers),
            services=len(services),
            service_interfaces=len(service_interfaces),
            repositories=len(repositories),
            entities=len(entities),
            dtos=len(dtos),
            applications=len(applications),
            endpoints=len(all_endpoints),
            relationships=len(final_relationships),
            packages=len(packages_list)
        )

        return Architecture(
            analysis_id=str(uuid.uuid4()),
            project=self.project_name,
            summary=summary,
            diagnostics=diagnostics,
            classes=all_classes_list,
            controllers=controllers,
            services=services,
            service_interfaces=service_interfaces,
            repositories=repositories,
            entities=entities,
            dtos=dtos,
            applications=applications,
            relationships=final_relationships,
            endpoints=all_endpoints,
            packages=packages_list,
            observations=observations,
            auth_info=auth_info,
            database_info=database_info
        )

    def _detect_database_vendor(self) -> Dict[str, Any]:
        vendor = None
        evidence: List[str] = []
        
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in DEFAULT_SKIPPED_DIRS and not d.startswith(".")]
            for file in files:
                fl = file.lower()
                rel_path = os.path.relpath(os.path.join(root, file), self.root_dir).replace("\\", "/")
                if fl in ["pom.xml", "build.gradle", "build.gradle.kts"] or fl.startswith("application.") or fl.startswith("application-"):
                    full_p = os.path.join(root, file)
                    try:
                        with open(full_p, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            
                        if "jdbc:postgresql:" in content or "org.postgresql" in content or "postgresql" in content:
                            if not vendor: vendor = "PostgreSQL"
                            if "jdbc:postgresql:" in content:
                                for line in content.splitlines():
                                    if "jdbc:postgresql:" in line:
                                        evidence.append(f"Found '{line.strip()}' in {rel_path}")
                            if "postgresql" in content and fl.endswith((".xml", ".gradle", ".kts")):
                                evidence.append(f"Found PostgreSQL dependency in {rel_path}")
                                
                        if "jdbc:mysql:" in content or "mysql-connector" in content or "mysql:" in content:
                            if not vendor: vendor = "MySQL"
                            if "jdbc:mysql:" in content:
                                for line in content.splitlines():
                                    if "jdbc:mysql:" in line:
                                        evidence.append(f"Found '{line.strip()}' in {rel_path}")
                            if "mysql" in content and fl.endswith((".xml", ".gradle", ".kts")):
                                evidence.append(f"Found MySQL dependency in {rel_path}")
                                
                        if "jdbc:h2:" in content or "com.h2database" in content:
                            if not vendor: vendor = "H2 Database"
                            if "jdbc:h2:" in content:
                                for line in content.splitlines():
                                    if "jdbc:h2:" in line:
                                        evidence.append(f"Found '{line.strip()}' in {rel_path}")
                            if "h2" in content and fl.endswith((".xml", ".gradle", ".kts")):
                                evidence.append(f"Found H2 dependency in {rel_path}")
                                
                        if "jdbc:mariadb:" in content or "mariadb-java-client" in content:
                            if not vendor: vendor = "MariaDB"
                            if "jdbc:mariadb:" in content:
                                for line in content.splitlines():
                                    if "jdbc:mariadb:" in line:
                                        evidence.append(f"Found '{line.strip()}' in {rel_path}")
                                        
                        if "jdbc:oracle:" in content or "ojdbc" in content:
                            if not vendor: vendor = "Oracle Database"
                            if "jdbc:oracle:" in content:
                                for line in content.splitlines():
                                    if "jdbc:oracle:" in line:
                                        evidence.append(f"Found '{line.strip()}' in {rel_path}")
                                        
                        if "jdbc:sqlserver:" in content or "mssql-jdbc" in content:
                            if not vendor: vendor = "Microsoft SQL Server"
                            if "jdbc:sqlserver:" in content:
                                for line in content.splitlines():
                                    if "jdbc:sqlserver:" in line:
                                        evidence.append(f"Found '{line.strip()}' in {rel_path}")
                                        
                        if "mongodb://" in content or "spring-boot-starter-data-mongodb" in content or "mongodb-driver" in content:
                            if not vendor: vendor = "MongoDB"
                            if "mongodb://" in content:
                                for line in content.splitlines():
                                    if "mongodb://" in line:
                                        evidence.append(f"Found '{line.strip()}' in {rel_path}")
                            if "mongodb" in content and fl.endswith((".xml", ".gradle", ".kts")):
                                evidence.append(f"Found MongoDB dependency in {rel_path}")
                    except Exception:
                        pass

        return {
            "detected": bool(vendor),
            "vendor": vendor,
            "evidence": list(dict.fromkeys(evidence))
        }

    def _detect_authentication(self, classes_map: Dict[str, ClassInfo]) -> Dict[str, Any]:
        components: List[str] = []
        dependencies: List[str] = []
        evidence: List[str] = []
        
        # 1. Scan Java classes for security annotations and classes
        for fqn, c in classes_map.items():
            annos = set(c.annotations)
            if any(a in annos for a in ["EnableWebSecurity", "EnableMethodSecurity", "EnableGlobalMethodSecurity", "Secured", "PreAuthorize"]):
                components.append(c.name)
                evidence.append(f"Class `{c.name}` ({c.file}) has security annotations: {', '.join(annos & {'EnableWebSecurity', 'EnableMethodSecurity', 'EnableGlobalMethodSecurity', 'Secured', 'PreAuthorize'})}")
            elif c.name.startswith(("Auth", "Security", "Jwt", "Token")) or c.name.endswith(("Auth", "Security", "Filter", "Provider", "UserDetailsService")):
                if c.type in ["service", "service_interface", "controller", "component", "configuration"] or "Filter" in c.name or "Provider" in c.name or "UserDetailsService" in c.name or "Token" in c.name:
                    components.append(c.name)
                    evidence.append(f"Class `{c.name}` ({c.file}) implements security/auth role ({c.type})")
            elif any(imp in ["UserDetailsService", "AuthenticationManager", "SecurityFilterChain"] for imp in c.implements) or (c.extends and "Filter" in c.extends):
                components.append(c.name)
                evidence.append(f"Class `{c.name}` ({c.file}) extends/implements {c.extends or ', '.join(c.implements)}")

        # 2. Scan build files for dependencies
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in DEFAULT_SKIPPED_DIRS and not d.startswith(".")]
            for file in files:
                fl = file.lower()
                if fl in ["pom.xml", "build.gradle", "build.gradle.kts"]:
                    full_p = os.path.join(root, file)
                    rel_path = os.path.relpath(full_p, self.root_dir).replace("\\", "/")
                    try:
                        with open(full_p, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        if "spring-boot-starter-security" in content or "spring-security" in content:
                            dependencies.append("spring-boot-starter-security")
                            evidence.append(f"Found Spring Security dependency in {rel_path}")
                        if "jjwt" in content or "jwt" in content.lower():
                            dependencies.append("jjwt")
                            evidence.append(f"Found JWT dependency in {rel_path}")
                        if "spring-security-oauth2" in content or "oauth2" in content.lower():
                            dependencies.append("spring-security-oauth2")
                            evidence.append(f"Found OAuth2 dependency in {rel_path}")
                    except Exception:
                        pass

        detected = bool(components or dependencies)
        return {
            "detected": detected,
            "components": list(dict.fromkeys(components)),
            "dependencies": list(dict.fromkeys(dependencies)),
            "evidence": list(dict.fromkeys(evidence))
        }
