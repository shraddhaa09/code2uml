import os
import re
from typing import List, Dict, Set, Optional
from backend.analyzer.models import (
    ClassInfo,
    FieldInfo,
    MethodInfo,
    MethodParamInfo,
    EndpointInfo,
    RelationshipInfo,
    ArchitectureSummary,
    Observation,
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


class ProjectAnalyzer:
    """Deterministic Java & Spring Boot static architecture analyzer."""

    def __init__(self, root_dir: str, project_name: Optional[str] = None):
        self.root_dir = os.path.abspath(root_dir)
        self.project_name = project_name or os.path.basename(self.root_dir)

    def analyze(self) -> Architecture:
        # Step 1: Scan all .java files
        java_files: List[str] = []
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in {".git", "target", "build", ".gradle", "bin", ".idea", "node_modules"}]
            for file in files:
                if file.endswith(".java"):
                    java_files.append(os.path.join(root, file))

        parsed_files: List[JavaParsedFile] = []
        for jfile in java_files:
            rel_path = os.path.relpath(jfile, self.root_dir).replace("\\", "/")
            parsed = JavaParser.parse_file(jfile, rel_path)
            parsed_files.append(parsed)

        # Step 2: First pass - collect all discovered types
        discovered_types: Dict[str, Dict] = {}
        distinct_packages: Set[str] = set()

        for pfile in parsed_files:
            if pfile.package:
                distinct_packages.add(pfile.package)
            for t in pfile.types:
                t_name = t["name"]
                discovered_types[t_name] = {
                    "raw": t,
                    "package": pfile.package,
                    "file": pfile.relative_path,
                    "imports": pfile.imports
                }

        # Step 3: Classify types and extract rich metadata
        classes_map: Dict[str, ClassInfo] = {}
        controllers: List[ClassInfo] = []
        services: List[ClassInfo] = []
        service_interfaces: List[ClassInfo] = []
        repositories: List[ClassInfo] = []
        entities: List[ClassInfo] = []
        dtos: List[ClassInfo] = []
        applications: List[ClassInfo] = []
        all_endpoints: List[EndpointInfo] = []

        for name, data in discovered_types.items():
            raw = data["raw"]
            pkg = data["package"]
            file_rel = data["file"]
            annos = raw.get("annotations", [])
            anno_attrs = raw.get("annotation_attributes", {})
            anno_set = set(annos)
            is_interface = bool(raw.get("is_interface", False))

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
            if raw.get("extends") and "Repository" in raw["extends"]:
                gen_args = extract_all_generic_args(raw["extends"])
                if gen_args:
                    managed_entity = gen_args[0]

            # Determine type
            ctype = "class"
            if "SpringBootApplication" in anno_set:
                ctype = "application"
            elif "RestController" in anno_set or "Controller" in anno_set:
                ctype = "controller"
            elif "Service" in anno_set and not is_interface:
                ctype = "service"
            elif is_interface and ("Repository" in anno_set or (raw.get("extends") and "Repository" in raw["extends"]) or "repository" in pkg.lower() or name.endswith("Repository")):
                ctype = "repository"
            elif is_interface and ("service" in pkg.lower() or name.endswith("Service")):
                ctype = "service_interface"
            elif is_interface:
                ctype = "interface"
            elif "Repository" in anno_set or (raw.get("extends") and "Repository" in raw["extends"]):
                ctype = "repository"
            elif "Entity" in anno_set or "Table" in anno_set or "Document" in anno_set:
                ctype = "entity"
            elif "Configuration" in anno_set:
                ctype = "configuration"
            elif "Component" in anno_set:
                ctype = "component"
            elif "dto" in pkg.lower() or name.endswith("DTO") or name.endswith("Dto") or name.endswith("Request") or name.endswith("Response"):
                ctype = "dto"
            elif name.endswith("Service") or name.endswith("ServiceImpl"):
                ctype = "service" if not is_interface else "service_interface"
            elif name.endswith("Repository"):
                ctype = "repository"
            elif name.endswith("Controller"):
                ctype = "controller"

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
                managed_entity=managed_entity
            )
            classes_map[name] = class_info

        # Step 4: Detect raw candidate relationships
        candidate_rels: List[RelationshipInfo] = []

        def add_candidate(source: str, target: str, rel_type: str, desc: Optional[str] = None):
            if source != target and target in discovered_types:
                candidate_rels.append(RelationshipInfo(
                    source=source,
                    target=target,
                    type=rel_type,
                    description=desc
                ))

        for name, data in discovered_types.items():
            raw = data["raw"]
            cinfo = classes_map[name]
            deps: Set[str] = set()

            # 1. Constructor dependencies
            for ctor in raw.get("constructors", []):
                for param in ctor.get("parameters", []):
                    ptype = extract_base_type(param.get("type", ""))
                    if ptype in discovered_types and ptype != name:
                        deps.add(ptype)
                        add_candidate(name, ptype, "dependency", "injected via constructor")

            # 2. Field dependencies
            for f in raw.get("fields", []):
                ftype = extract_base_type(f.get("type", ""))
                fannos = set(f.get("annotations", []))
                is_injected = ("Autowired" in fannos or "Inject" in fannos or "Resource" in fannos)
                if ftype in discovered_types and ftype != name:
                    deps.add(ftype)
                    rel_desc = "injected via field" if is_injected else "references field"
                    add_candidate(name, ftype, "dependency", rel_desc)

            # 3. Implements interface relationships
            for imp in raw.get("implements", []):
                clean_imp = extract_base_type(imp)
                if clean_imp in discovered_types:
                    add_candidate(name, clean_imp, "implements", f"implements {clean_imp}")

            # 4. Extends relationships
            if raw.get("extends"):
                raw_extends = raw["extends"]
                base_ext_name = raw_extends.split("<")[0].strip()
                if base_ext_name in discovered_types:
                    add_candidate(name, base_ext_name, "extends", f"extends {base_ext_name}")

                # Check if repository manages entity via generic argument
                if "Repository" in raw_extends:
                    generic_args = extract_all_generic_args(raw_extends)
                    for g_arg in generic_args:
                        if g_arg in discovered_types and classes_map.get(g_arg) and classes_map[g_arg].type == "entity":
                            deps.add(g_arg)
                            add_candidate(name, g_arg, "manages_entity", f"repository manages {g_arg}")

            # 5. Method parameter/return type DTO/Entity usages
            for m in raw.get("declared_methods", []):
                m_ret = extract_base_type(m.get("return_type", ""))
                if m_ret in discovered_types and m_ret != name:
                    target_info = classes_map.get(m_ret)
                    if target_info and target_info.type in ["dto", "entity"]:
                        rel_t = "uses_dto" if target_info.type == "dto" else "uses_entity"
                        add_candidate(name, m_ret, rel_t, f"method {m['name']} returns {m_ret}")

                for p in m.get("parameters", []):
                    ptype = extract_base_type(p.get("type", ""))
                    if ptype in discovered_types and ptype != name:
                        target_info = classes_map.get(ptype)
                        if target_info and target_info.type in ["dto", "entity"]:
                            rel_t = "uses_dto" if target_info.type == "dto" else "uses_entity"
                            add_candidate(name, ptype, rel_t, f"method {m['name']} accepts {ptype}")

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

        # Step 5: Deduplicate and filter relationships
        # Rule: If a stronger relationship (dependency, implements, extends, manages_entity)
        # exists between a (source, target) pair, suppress the generic uses/uses_dto/uses_entity edge.
        STRONG_REL_TYPES = {"dependency", "implements", "extends", "manages_entity", "manages", "injects"}
        GENERIC_USES_TYPES = {"uses", "uses_dto", "uses_entity"}

        pair_has_strong: Set[Tuple[str, str]] = set()
        for r in candidate_rels:
            if r.type in STRONG_REL_TYPES:
                pair_has_strong.add((r.source, r.target))

        final_relationships: List[RelationshipInfo] = []
        seen_rel_signatures: Set[str] = set()

        for r in candidate_rels:
            # If pair already has a strong relationship and this is a generic 'uses' edge, suppress it
            if (r.source, r.target) in pair_has_strong and r.type in GENERIC_USES_TYPES:
                continue

            sig = f"{r.source}->{r.target}:{r.type}"
            if sig not in seen_rel_signatures:
                seen_rel_signatures.add(sig)
                final_relationships.append(r)

        # Step 6: Architecture Observations (Deterministic Rules)
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
        all_implemented_ifaces = set()
        for s in services:
            all_implemented_ifaces.update(s.implements)
        for si in service_interfaces:
            if si.name not in all_implemented_ifaces:
                observations.append(Observation(
                    severity="info",
                    message=f"Service interface {si.name} has no implementing class detected in the codebase.",
                    components=[si.name]
                ))

        # Step 7: Summary counts
        all_classes_list = list(classes_map.values())
        class_count = sum(1 for c in all_classes_list if not c.is_interface)
        interface_count = sum(1 for c in all_classes_list if c.is_interface)
        packages_list = sorted(list(distinct_packages))

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
            project=self.project_name,
            summary=summary,
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
            observations=observations
        )
