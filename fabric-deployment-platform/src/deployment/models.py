"""
Data models for Microsoft Fabric deployment system.

This module defines all data structures used throughout the deployment
orchestration system, including results, status, and artifact collections.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ExitCode:
    """Standard exit codes for CLI and pipeline integration."""
    SUCCESS = 0
    VALIDATION_FAILED = 1
    DEPLOYMENT_FAILED = 2
    TERRAFORM_ERROR = 3
    CONFIGURATION_ERROR = 4
    ARTIFACT_ERROR = 5
    UNKNOWN_ERROR = 99


class DeploymentStatus(Enum):
    """Deployment status enumeration."""
    NOT_DEPLOYED = "not_deployed"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"
    DESTROYING = "destroying"


class ArtifactType(Enum):
    """Microsoft Fabric artifact types."""
    LAKEHOUSE = "lakehouse"
    PIPELINE = "pipeline"
    NOTEBOOK = "notebook"


class DeploymentPhase(Enum):
    """Deployment phases in order."""
    VALIDATION = "validation"
    PLANNING = "planning"
    INFRASTRUCTURE = "infrastructure"
    ARTIFACTS = "artifacts"
    VERIFICATION = "verification"


@dataclass
class ArtifactCollection:
    """Collection of artifacts to be deployed."""
    customer_name: str
    environment: str
    lakehouses: List[Path] = field(default_factory=list)
    pipelines: List[Path] = field(default_factory=list)
    notebooks: List[Path] = field(default_factory=list)
    
    @property
    def total_count(self) -> int:
        """Total number of artifacts."""
        return len(self.lakehouses) + len(self.pipelines) + len(self.notebooks)
    
    @property
    def all_artifacts(self) -> List[Path]:
        """All artifacts as a flat list."""
        return self.lakehouses + self.pipelines + self.notebooks
    
    def get_by_type(self, artifact_type: ArtifactType) -> List[Path]:
        """Get artifacts by type."""
        mapping = {
            ArtifactType.LAKEHOUSE: self.lakehouses,
            ArtifactType.PIPELINE: self.pipelines,
            ArtifactType.NOTEBOOK: self.notebooks
        }
        return mapping.get(artifact_type, [])


@dataclass
class ValidationResult:
    """Result of validation checks."""
    success: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checks_performed: List[str] = field(default_factory=list)
    
    @property
    def has_errors(self) -> bool:
        """Check if validation has errors."""
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if validation has warnings."""
        return len(self.warnings) > 0


@dataclass
class TerraformResult:
    """Result of Terraform operations."""
    success: bool
    command: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration: float = 0.0
    outputs: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


@dataclass
class TerraformPlan:
    """Terraform plan information."""
    customer_name: str
    environment: str
    plan_file: Optional[Path] = None
    changes: Dict[str, int] = field(default_factory=dict)  # add, change, destroy counts
    resources: List[str] = field(default_factory=list)
    has_changes: bool = False
    plan_output: str = ""


@dataclass
class DeploymentResult:
    """Result of a customer deployment."""
    customer_name: str
    environment: str
    status: DeploymentStatus
    success: bool
    artifacts_deployed: List[str] = field(default_factory=list)
    workspace_id: str = ""
    deployment_time: float = 0.0
    terraform_outputs: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    phases_completed: List[DeploymentPhase] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def add_error(self, error: str) -> None:
        """Add an error to the result."""
        self.errors.append(error)
        self.success = False
        self.status = DeploymentStatus.FAILED
    
    def add_warning(self, warning: str) -> None:
        """Add a warning to the result."""
        self.warnings.append(warning)


@dataclass
class BatchDeploymentResult:
    """Result of multiple customer deployments."""
    environment: str
    total_customers: int
    successful_deployments: List[DeploymentResult] = field(default_factory=list)
    failed_deployments: List[DeploymentResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def success_count(self) -> int:
        """Number of successful deployments."""
        return len(self.successful_deployments)
    
    @property
    def failure_count(self) -> int:
        """Number of failed deployments."""
        return len(self.failed_deployments)
    
    @property
    def overall_success(self) -> bool:
        """Whether all deployments succeeded."""
        return self.failure_count == 0


@dataclass
class DeploymentPlan:
    """Deployment plan for a customer."""
    customer_name: str
    environment: str
    artifacts: ArtifactCollection
    terraform_plan: TerraformPlan
    validation_result: ValidationResult
    estimated_duration: float = 0.0
    prerequisite_checks: List[str] = field(default_factory=list)


@dataclass
class PhaseResults:
    """Results of deployment phases."""
    validation: Optional[ValidationResult] = None
    planning: Optional[TerraformPlan] = None
    infrastructure: Optional[TerraformResult] = None
    artifacts: Optional[TerraformResult] = None
    verification: Optional[ValidationResult] = None
    
    @property
    def all_successful(self) -> bool:
        """Check if all phases completed successfully."""
        results = [self.validation, self.planning, self.infrastructure, 
                  self.artifacts, self.verification]
        return all(r is None or getattr(r, 'success', True) for r in results)


@dataclass
class PipelineConfig:
    """Pipeline configuration from environment variables."""
    customer_name: Optional[str] = None
    environment: str = "dev"
    build_id: Optional[str] = None
    source_branch: Optional[str] = None
    repository: Optional[str] = None
    output_dir: Path = Path("./deployment-outputs")
    
    @classmethod
    def from_environment(cls) -> 'PipelineConfig':
        """Create pipeline config from environment variables."""
        return cls(
            customer_name=os.getenv("CUSTOMER_NAME"),
            environment=os.getenv("TARGET_ENVIRONMENT", "dev"),
            build_id=os.getenv("BUILD_BUILDID"),
            source_branch=os.getenv("BUILD_SOURCEBRANCH"),
            repository=os.getenv("BUILD_REPOSITORY_NAME"),
            output_dir=Path(os.getenv("PIPELINE_WORKSPACE", "./deployment-outputs"))
        )


@dataclass
class DeploymentReport:
    """Comprehensive deployment report."""
    customer_name: str
    environment: str
    deployment_result: DeploymentResult
    artifacts_summary: Dict[str, int] = field(default_factory=dict)
    terraform_summary: Dict[str, Any] = field(default_factory=dict)
    validation_summary: Dict[str, int] = field(default_factory=dict)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for serialization."""
        return {
            "customer_name": self.customer_name,
            "environment": self.environment,
            "success": self.deployment_result.success,
            "status": self.deployment_result.status.value,
            "artifacts_deployed": self.deployment_result.artifacts_deployed,
            "deployment_time": self.deployment_result.deployment_time,
            "errors": self.deployment_result.errors,
            "warnings": self.deployment_result.warnings,
            "artifacts_summary": self.artifacts_summary,
            "terraform_summary": self.terraform_summary,
            "validation_summary": self.validation_summary,
            "performance_metrics": self.performance_metrics,
            "generated_at": self.generated_at.isoformat()
        }


@dataclass
class TerraformArtifacts:
    """Artifacts prepared for Terraform deployment."""
    variables: Dict[str, Any] = field(default_factory=dict)
    files: Dict[str, Path] = field(default_factory=dict)
    module_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContentValidation:
    """Result of artifact content validation."""
    valid_notebooks: List[Path] = field(default_factory=list)
    invalid_notebooks: List[Path] = field(default_factory=list)
    validation_errors: Dict[str, List[str]] = field(default_factory=dict)
    
    @property
    def is_valid(self) -> bool:
        """Check if all content is valid."""
        return len(self.invalid_notebooks) == 0


@dataclass
class ArtifactValidation:
    """Result of artifact existence validation."""
    missing_artifacts: List[str] = field(default_factory=list)
    found_artifacts: List[Path] = field(default_factory=list)
    
    @property
    def all_present(self) -> bool:
        """Check if all required artifacts are present."""
        return len(self.missing_artifacts) == 0


@dataclass
class DeploymentOrder:
    """Deployment order configuration."""
    phases: List[str] = field(default_factory=list)
    templates: Dict[str, Dict[str, str]] = field(default_factory=dict)
    
    def get_phase_templates(self, phase: str) -> Dict[str, str]:
        """Get templates for a specific phase."""
        return self.templates.get(phase, {})


@dataclass
class PrerequisiteCheck:
    """Result of prerequisite validation."""
    terraform_available: bool = False
    configuration_valid: bool = False
    artifacts_present: bool = False
    workspace_accessible: bool = False
    credentials_valid: bool = False
    
    @property
    def all_met(self) -> bool:
        """Check if all prerequisites are met."""
        return all([
            self.terraform_available,
            self.configuration_valid,
            self.artifacts_present,
            self.workspace_accessible,
            self.credentials_valid
        ])
    
    @property
    def failed_checks(self) -> List[str]:
        """Get list of failed prerequisite checks."""
        checks = [
            ("terraform_available", self.terraform_available),
            ("configuration_valid", self.configuration_valid),
            ("artifacts_present", self.artifacts_present),
            ("workspace_accessible", self.workspace_accessible),
            ("credentials_valid", self.credentials_valid)
        ]
        return [name for name, passed in checks if not passed]


class DeploymentException(Exception):
    """Base exception for deployment errors."""
    pass


class ValidationException(DeploymentException):
    """Exception for validation failures."""
    pass


class TerraformException(DeploymentException):
    """Exception for Terraform operation failures."""
    pass


class ArtifactException(DeploymentException):
    """Exception for artifact-related failures."""
    pass


class ConfigurationException(DeploymentException):
    """Exception for configuration-related failures."""
    pass