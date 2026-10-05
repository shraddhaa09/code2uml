from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class FieldInfo(BaseModel):
    name: str
    type: str
    annotations: List[str] = Field(default_factory=list)
    annotation_attributes: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    is_id: bool = False


class MethodParamInfo(BaseModel):
    name: str
    type: str


class MethodInfo(BaseModel):
    name: str
    return_type: str = "void"
    parameters: List[MethodParamInfo] = Field(default_factory=list)
    signature: str = ""
    annotations: List[str] = Field(default_factory=list)
    annotation_attributes: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class EndpointInfo(BaseModel):
    http_method: str
    path: str
    method_name: str
    return_type: Optional[str] = None
    controller: str


class ClassInfo(BaseModel):
    name: str
    package: str
    type: str  # "controller", "service", "service_interface", "repository", "entity", "dto", "application", "configuration", "component", "interface", "class"
    is_interface: bool = False
    annotations: List[str] = Field(default_factory=list)
    annotation_attributes: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    implements: List[str] = Field(default_factory=list)
    extends: Optional[str] = None
    file: str
    endpoints: List[EndpointInfo] = Field(default_factory=list)
    methods: List[str] = Field(default_factory=list)
    declared_methods: List[MethodInfo] = Field(default_factory=list)
    fields: List[FieldInfo] = Field(default_factory=list)
    base_path: Optional[str] = None
    table_name: Optional[str] = None
    managed_entity: Optional[str] = None
    detection_heuristic: Optional[str] = None


class RelationshipInfo(BaseModel):
    source: str
    target: str
    type: str  # "dependency", "implements", "extends", "manages_entity", "uses_dto", "uses_entity"
    description: Optional[str] = None


class ArchitectureSummary(BaseModel):
    total_types: int = 0
    total_classes: int = 0  # backwards compatibility alias
    classes: int = 0
    interfaces: int = 0
    controllers: int = 0
    services: int = 0
    service_interfaces: int = 0
    repositories: int = 0
    entities: int = 0
    dtos: int = 0
    applications: int = 0
    endpoints: int = 0
    relationships: int = 0
    packages: int = 0


class Observation(BaseModel):
    severity: str = "warning"  # "warning", "info", "caution"
    message: str
    components: List[str] = Field(default_factory=list)


class FileParseDiagnostic(BaseModel):
    file: str
    method: str  # "ast", "fallback", "failed", "unsupported", "skipped"
    types_count: int = 0
    error: Optional[str] = None


class AnalysisDiagnostics(BaseModel):
    total_files_discovered: int = 0
    parsed_ast_count: int = 0
    parsed_fallback_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    unsupported_languages: Dict[str, int] = Field(default_factory=dict)
    coverage_percentage: float = 100.0
    warnings: List[str] = Field(default_factory=list)
    file_details: List[FileParseDiagnostic] = Field(default_factory=list)


class Architecture(BaseModel):
    analysis_id: Optional[str] = None
    project: str
    summary: ArchitectureSummary
    diagnostics: AnalysisDiagnostics = Field(default_factory=AnalysisDiagnostics)
    classes: List[ClassInfo] = Field(default_factory=list)
    controllers: List[ClassInfo] = Field(default_factory=list)
    services: List[ClassInfo] = Field(default_factory=list)
    service_interfaces: List[ClassInfo] = Field(default_factory=list)
    repositories: List[ClassInfo] = Field(default_factory=list)
    entities: List[ClassInfo] = Field(default_factory=list)
    dtos: List[ClassInfo] = Field(default_factory=list)
    applications: List[ClassInfo] = Field(default_factory=list)
    relationships: List[RelationshipInfo] = Field(default_factory=list)
    endpoints: List[EndpointInfo] = Field(default_factory=list)
    packages: List[str] = Field(default_factory=list)
    observations: List[Observation] = Field(default_factory=list)
    auth_info: Dict[str, Any] = Field(default_factory=dict)
    database_info: Dict[str, Any] = Field(default_factory=dict)


