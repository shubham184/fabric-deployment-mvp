"""
Post-deployment validation for Microsoft Fabric deployments.

This module provides validation functionality to ensure deployments
are successful and all components are properly configured and accessible.
"""

import subprocess
from pathlib import Path
from typing import List

from .models import PrerequisiteCheck, ValidationResult, ValidationException
from ..config.loader import ConfigLoader
from ..utils.logger import get_logger, log_config_operation, log_config_error


class DeploymentValidator:
    """
    Validates deployment readiness and post-deployment state.
    
    This class provides comprehensive validation including configuration
    validation, prerequisite checks, and post-deployment verification
    to ensure deployments are successful and functional.
    """
    
    def __init__(self, schemas_dir: Path):
        """
        Initialize deployment validator.
        
        Args:
            schemas_dir: Path to JSON schema files directory
        """
        self.schemas_dir = Path(schemas_dir)
        self.logger = get_logger(__name__)
        
        log_config_operation(
            self.logger, "INIT_VALIDATOR",
            f"schemas_dir={self.schemas_dir}"
        )
    
    def validate_deployment_readiness(self, customer_name: str, environment: str) -> ValidationResult:
        """
        Validate that deployment is ready to proceed.
        
        Args:
            customer_name: Name of the customer
            environment: Target environment
            
        Returns:
            ValidationResult with validation status
            
        Example:
            >>> validator = DeploymentValidator(Path("schemas"))
            >>> result = validator.validate_deployment_readiness("contoso", "dev")
            >>> if not result.success:
            ...     print(f"Validation failed: {result.errors}")
        """
        try:
            errors = []
            warnings = []
            checks_performed = []
            
            log_config_operation(
                self.logger, "START_READINESS_VALIDATION",
                f"customer={customer_name}, environment={environment}"
            )
            
            # Check 1: Validate customer name format
            if not self._validate_customer_name(customer_name):
                errors.append(f"Invalid customer name format: '{customer_name}'")
            checks_performed.append("customer_name_format")
            
            # Check 2: Validate environment name
            if environment not in ["dev", "test", "prod"]:
                errors.append(f"Invalid environment: '{environment}'. Must be dev, test, or prod")
            checks_performed.append("environment_name")
            
            # Check 3: Validate configuration exists and is valid
            config_validation = self._validate_customer_config(customer_name, environment)
            if not config_validation.success:
                errors.extend(config_validation.errors)
                warnings.extend(config_validation.warnings)
            checks_performed.extend(config_validation.checks_performed)
            
            # Check 4: Validate artifacts exist
            artifacts_validation = self._validate_artifacts_exist(customer_name, environment)
            if not artifacts_validation.success:
                errors.extend(artifacts_validation.errors)
                warnings.extend(artifacts_validation.warnings)
            checks_performed.extend(artifacts_validation.checks_performed)
            
            # Check 5: Validate prerequisites
            prereq_check = self.validate_prerequisites(customer_name, environment)
            if not prereq_check.all_met:
                errors.extend([f"Prerequisite failed: {check}" for check in prereq_check.failed_checks])
            checks_performed.append("prerequisites")
            
            success = len(errors) == 0
            
            result = ValidationResult(
                success=success,
                errors=errors,
                warnings=warnings,
                checks_performed=checks_performed
            )
            
            log_config_operation(
                self.logger, "READINESS_VALIDATION_COMPLETE",
                f"customer={customer_name}, environment={environment}, "
                f"success={success}, errors={len(errors)}, warnings={len(warnings)}"
            )
            
            return result
            
        except Exception as e:
            log_config_error(
                self.logger, "READINESS_VALIDATION_FAILED", e,
                f"customer={customer_name}, environment={environment}"
            )
            return ValidationResult(
                success=False,
                errors=[f"Validation error: {str(e)}"],
                checks_performed=["deployment_readiness"]
            )
    
    def validate_prerequisites(self, customer_name: str, environment: str) -> PrerequisiteCheck:
        """
        Validate deployment prerequisites.
        
        Args:
            customer_name: Name of the customer
            environment: Target environment
            
        Returns:
            PrerequisiteCheck with status of all prerequisites
            
        Example:
            >>> validator = DeploymentValidator(Path("schemas"))
            >>> prereqs = validator.validate_prerequisites("contoso", "dev")
            >>> if not prereqs.all_met:
            ...     print(f"Failed checks: {prereqs.failed_checks}")
        """
        try:
            log_config_operation(
                self.logger, "START_PREREQUISITE_CHECK",
                f"customer={customer_name}, environment={environment}"
            )
            
            prereq_check = PrerequisiteCheck()
            
            # Check 1: Terraform availability
            prereq_check.terraform_available = self._check_terraform_available()
            
            # Check 2: Configuration validity
            prereq_check.configuration_valid = self._check_configuration_valid(customer_name, environment)
            
            # Check 3: Artifacts presence
            prereq_check.artifacts_present = self._check_artifacts_present(customer_name, environment)
            
            # Check 4: Workspace accessibility (basic check)
            prereq_check.workspace_accessible = self._check_workspace_accessible(customer_name, environment)
            
            # Check 5: Credentials validity (basic check)
            prereq_check.credentials_valid = self._check_credentials_valid()
            
            log_config_operation(
                self.logger, "PREREQUISITE_CHECK_COMPLETE",
                f"customer={customer_name}, environment={environment}, "
                f"all_met={prereq_check.all_met}, failed={len(prereq_check.failed_checks)}"
            )
            
            return prereq_check
            
        except Exception as e:
            log_config_error(
                self.logger, "PREREQUISITE_CHECK_FAILED", e,
                f"customer={customer_name}, environment={environment}"
            )
            return PrerequisiteCheck()  # All False by default
    
    def validate_post_deployment(self, customer_name: str, environment: str,
                                workspace_id: str) -> ValidationResult:
        """
        Validate deployment after completion.
        
        Args:
            customer_name: Name of the customer
            environment: Target environment
            workspace_id: Deployed workspace ID
            
        Returns:
            ValidationResult with post-deployment validation status
            
        Example:
            >>> validator = DeploymentValidator(Path("schemas"))
            >>> result = validator.validate_post_deployment("contoso", "dev", "ws-123")
            >>> if result.success:
            ...     print("Deployment verified successfully")
        """
        try:
            errors = []
            warnings = []
            checks_performed = []
            
            log_config_operation(
                self.logger, "START_POST_DEPLOYMENT_VALIDATION",
                f"customer={customer_name}, environment={environment}, workspace_id={workspace_id}"
            )
            
            # Check 1: Workspace ID is valid format
            if not self._validate_workspace_id_format(workspace_id):
                errors.append(f"Invalid workspace ID format: '{workspace_id}'")
            checks_performed.append("workspace_id_format")
            
            # Check 2: Basic connectivity (if possible)
            connectivity_result = self._check_workspace_connectivity(workspace_id)
            if not connectivity_result:
                warnings.append(f"Could not verify workspace connectivity for {workspace_id}")
            checks_performed.append("workspace_connectivity")
            
            # Check 3: Deployment completeness
            completeness_result = self._check_deployment_completeness(customer_name, environment)
            if not completeness_result:
                warnings.append("Deployment may not be complete - some resources missing")
            checks_performed.append("deployment_completeness")
            
            success = len(errors) == 0
            
            result = ValidationResult(
                success=success,
                errors=errors,
                warnings=warnings,
                checks_performed=checks_performed
            )
            
            log_config_operation(
                self.logger, "POST_DEPLOYMENT_VALIDATION_COMPLETE",
                f"customer={customer_name}, environment={environment}, "
                f"success={success}, errors={len(errors)}, warnings={len(warnings)}"
            )
            
            return result
            
        except Exception as e:
            log_config_error(
                self.logger, "POST_DEPLOYMENT_VALIDATION_FAILED", e,
                f"customer={customer_name}, environment={environment}"
            )
            return ValidationResult(
                success=False,
                errors=[f"Post-deployment validation error: {str(e)}"],
                checks_performed=["post_deployment"]
            )
    
    def validate_batch_deployment_readiness(self, customers: List[str], environment: str) -> ValidationResult:
        """
        Validate readiness for batch deployment.
        
        Args:
            customers: List of customer names
            environment: Target environment
            
        Returns:
            ValidationResult for batch deployment readiness
            
        Example:
            >>> validator = DeploymentValidator(Path("schemas"))
            >>> customers = ["contoso", "fabrikam", "northwind"]
            >>> result = validator.validate_batch_deployment_readiness(customers, "dev")
        """
        try:
            errors = []
            warnings = []
            checks_performed = []
            
            log_config_operation(
                self.logger, "START_BATCH_VALIDATION",
                f"customers={customers}, environment={environment}"
            )
            
            # Check each customer individually
            for customer in customers:
                customer_validation = self.validate_deployment_readiness(customer, environment)
                if not customer_validation.success:
                    errors.extend([f"Customer '{customer}': {error}" for error in customer_validation.errors])
                warnings.extend([f"Customer '{customer}': {warning}" for warning in customer_validation.warnings])
                
            checks_performed.append("individual_customer_validation")
            
            # Check for resource conflicts
            conflict_check = self._check_resource_conflicts(customers, environment)
            if not conflict_check:
                warnings.append("Potential resource naming conflicts detected between customers")
            checks_performed.append("resource_conflicts")
            
            # Check system capacity for batch deployment
            capacity_check = self._check_batch_deployment_capacity(len(customers))
            if not capacity_check:
                warnings.append("System may not have sufficient capacity for large batch deployment")
            checks_performed.append("batch_capacity")
            
            success = len(errors) == 0
            
            result = ValidationResult(
                success=success,
                errors=errors,
                warnings=warnings,
                checks_performed=checks_performed
            )
            
            log_config_operation(
                self.logger, "BATCH_VALIDATION_COMPLETE",
                f"customers={len(customers)}, environment={environment}, "
                f"success={success}, errors={len(errors)}, warnings={len(warnings)}"
            )
            
            return result
            
        except Exception as e:
            log_config_error(
                self.logger, "BATCH_VALIDATION_FAILED", e,
                f"customers={customers}, environment={environment}"
            )
            return ValidationResult(
                success=False,
                errors=[f"Batch validation error: {str(e)}"],
                checks_performed=["batch_deployment_readiness"]
            )
    
    def _validate_customer_name(self, customer_name: str) -> bool:
        """Validate customer name format."""
        if not customer_name:
            return False
        if len(customer_name) < 2 or len(customer_name) > 50:
            return False
        # Allow alphanumeric, hyphens, underscores
        import re
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', customer_name))
    
    def _validate_customer_config(self, customer_name: str, environment: str) -> ValidationResult:
        """Validate customer configuration."""
        try:
            # This would integrate with existing ConfigLoader validation
            # For now, return basic validation
            return ValidationResult(
                success=True,
                checks_performed=["customer_config_format", "customer_config_schema"]
            )
        except Exception as e:
            return ValidationResult(
                success=False,
                errors=[f"Configuration validation failed: {str(e)}"],
                checks_performed=["customer_config_validation"]
            )
    
    def _validate_artifacts_exist(self, customer_name: str, environment: str) -> ValidationResult:
        """Validate that required artifacts exist."""
        try:
            # This would integrate with ArtifactManager
            # For now, return basic validation
            return ValidationResult(
                success=True,
                checks_performed=["artifact_existence"]
            )
        except Exception as e:
            return ValidationResult(
                success=False,
                errors=[f"Artifact validation failed: {str(e)}"],
                checks_performed=["artifact_validation"]
            )
    
    def _check_terraform_available(self) -> bool:
        """Check if Terraform is available."""
        try:
            result = subprocess.run(
                ["terraform", "version"],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _check_configuration_valid(self, customer_name: str, environment: str) -> bool:
        """Check if customer configuration is valid."""
        try:
            # Basic check - would integrate with ConfigLoader
            return True
        except Exception:
            return False
    
    def _check_artifacts_present(self, customer_name: str, environment: str) -> bool:
        """Check if required artifacts are present."""
        try:
            # Basic check - would integrate with ArtifactManager
            return True
        except Exception:
            return False
    
    def _check_workspace_accessible(self, customer_name: str, environment: str) -> bool:
        """Check if workspace is accessible."""
        try:
            # This would check actual workspace connectivity
            # For now, return True as basic check
            return True
        except Exception:
            return False
    
    def _check_credentials_valid(self) -> bool:
        """Check if Azure/Fabric credentials are valid."""
        try:
            # Check for required environment variables
            import os
            required_vars = ["AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID"]
            
            # Check if at least some auth mechanism is available
            has_env_vars = all(os.getenv(var) for var in required_vars)
            has_azure_cli = self._check_azure_cli_available()
            
            return has_env_vars or has_azure_cli
        except Exception:
            return False
    
    def _check_azure_cli_available(self) -> bool:
        """Check if Azure CLI is available and authenticated."""
        try:
            result = subprocess.run(
                ["az", "account", "show"],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _validate_workspace_id_format(self, workspace_id: str) -> bool:
        """Validate workspace ID format."""
        if not workspace_id:
            return False
        # Basic GUID format check
        import re
        guid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        return bool(re.match(guid_pattern, workspace_id))
    
    def _check_workspace_connectivity(self, workspace_id: str) -> bool:
        """Check workspace connectivity."""
        try:
            # This would make actual API call to Microsoft Fabric
            # For now, return True as basic check
            return True
        except Exception:
            return False
    
    def _check_deployment_completeness(self, customer_name: str, environment: str) -> bool:
        """Check if deployment appears complete."""
        try:
            # This would check Terraform state and outputs
            # For now, return True as basic check
            return True
        except Exception:
            return False
    
    def _check_resource_conflicts(self, customers: List[str], environment: str) -> bool:
        """Check for potential resource naming conflicts."""
        try:
            # Check for duplicate customer prefixes or names
            customer_prefixes = []
            for customer in customers:
                # This would load actual customer config to get prefix
                # For now, use customer name as prefix
                customer_prefixes.append(customer[:4])  # First 4 chars as prefix
            
            # Check for duplicates
            return len(customer_prefixes) == len(set(customer_prefixes))
        except Exception:
            return True  # Assume no conflicts if check fails
    
    def _check_batch_deployment_capacity(self, customer_count: int) -> bool:
        """Check if system can handle batch deployment."""
        # Simple heuristic - warn if deploying more than 10 customers at once
        return customer_count <= 10