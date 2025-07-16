"""
Terraform integration wrapper for Microsoft Fabric deployment.

This module provides the TerraformWrapper class that handles all Terraform
operations including init, plan, apply, and destroy, with proper state
management and Azure DevOps pipeline integration.
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from python_terraform import IsFlagged, IsNotFlagged, Terraform

from .models import (
    ArtifactCollection, TerraformArtifacts, TerraformPlan, TerraformResult,
    ValidationResult, TerraformException
)
from ..utils.logger import get_logger, log_config_operation, log_config_error


class TerraformWrapper:
    """
    Wrapper for Terraform operations with pipeline integration.
    
    This class provides a clean interface to Terraform operations,
    handles state management, generates variables from configuration,
    and integrates with Azure DevOps pipelines.
    """
    
    def __init__(self, terraform_dir: Path, state_backend: str = "local"):
        """
        Initialize Terraform wrapper.
        
        Args:
            terraform_dir: Path to Terraform configuration directory
            state_backend: State backend type ("local", "azurerm", "s3")
            
        Raises:
            TerraformException: If Terraform directory doesn't exist or Terraform not found
        """
        self.terraform_dir = Path(terraform_dir)
        self.state_backend = state_backend
        self.logger = get_logger(__name__)
        
        if not self.terraform_dir.exists():
            raise TerraformException(f"Terraform directory not found: {self.terraform_dir}")
        
        # Initialize Terraform client
        self.tf = Terraform(working_dir=str(self.terraform_dir))
        
        # Verify Terraform is available
        if not self._check_terraform_available():
            raise TerraformException("Terraform executable not found in PATH")
        
        log_config_operation(
            self.logger, "INIT_TERRAFORM",
            f"terraform_dir={self.terraform_dir}, backend={self.state_backend}"
        )
    
    def init(self, customer_name: str, environment: str) -> TerraformResult:
        """
        Initialize Terraform for customer/environment.
        
        Args:
            customer_name: Name of the customer
            environment: Target environment
            
        Returns:
            TerraformResult with initialization results
            
        Raises:
            TerraformException: If initialization fails
            
        Example:
            >>> wrapper = TerraformWrapper(Path("infrastructure"))
            >>> result = wrapper.init("contoso", "dev")
            >>> if result.success:
            ...     print("Terraform initialized successfully")
        """
        try:
            start_time = time.time()
            
            # Prepare backend configuration
            backend_config = self._get_backend_config(customer_name, environment)
            
            # Run terraform init
            return_code, stdout, stderr = self.tf.init(
                backend_config=backend_config,
                capture_output=True
            )
            
            duration = time.time() - start_time
            success = return_code == 0
            
            result = TerraformResult(
                success=success,
                command="init",
                exit_code=return_code,
                stdout=stdout,
                stderr=stderr,
                duration=duration
            )
            
            if not success:
                result.errors.append(f"Terraform init failed: {stderr}")
            
            log_config_operation(
                self.logger, "TERRAFORM_INIT",
                f"customer={customer_name}, environment={environment}, "
                f"success={success}, duration={duration:.2f}s"
            )
            
            return result
            
        except Exception as e:
            log_config_error(
                self.logger, "TERRAFORM_INIT", e,
                f"customer={customer_name}, environment={environment}"
            )
            raise TerraformException(f"Terraform init failed: {str(e)}")
    
    def plan(self, customer_name: str, environment: str, artifacts: ArtifactCollection) -> TerraformPlan:
        """
        Create Terraform plan for deployment.
        
        Args:
            customer_name: Name of the customer
            environment: Target environment
            artifacts: Collection of artifacts to deploy
            
        Returns:
            TerraformPlan with plan details
            
        Raises:
            TerraformException: If planning fails
            
        Example:
            >>> wrapper = TerraformWrapper(Path("infrastructure"))
            >>> plan = wrapper.plan("contoso", "dev", artifacts)
            >>> print(f"Plan has {plan.changes['add']} resources to add")
        """
        try:
            # Generate variables for this deployment
            tf_vars = self.generate_terraform_vars(customer_name, environment, artifacts)
            
            # Create plan file path
            plan_file = self._get_plan_file_path(customer_name, environment)
            
            # Run terraform plan
            return_code, stdout, stderr = self.tf.plan(
                var=tf_vars,
                out=str(plan_file),
                capture_output=True,
                detailed_exitcode=IsFlagged
            )
            
            # Parse plan output
            changes = self._parse_plan_output(stdout)
            resources = self._extract_resources_from_plan(stdout)
            has_changes = return_code == 2  # Terraform exit code 2 means changes present
            
            plan = TerraformPlan(
                customer_name=customer_name,
                environment=environment,
                plan_file=plan_file if return_code in [0, 2] else None,
                changes=changes,
                resources=resources,
                has_changes=has_changes,
                plan_output=stdout
            )
            
            if return_code not in [0, 2]:
                raise TerraformException(f"Terraform plan failed: {stderr}")
            
            log_config_operation(
                self.logger, "TERRAFORM_PLAN",
                f"customer={customer_name}, environment={environment}, "
                f"has_changes={has_changes}, changes={changes}"
            )
            
            return plan
            
        except Exception as e:
            log_config_error(
                self.logger, "TERRAFORM_PLAN", e,
                f"customer={customer_name}, environment={environment}"
            )
            raise TerraformException(f"Terraform plan failed: {str(e)}")
    
    def apply(self, customer_name: str, environment: str, artifacts: ArtifactCollection) -> TerraformResult:
        """
        Apply Terraform configuration.
        
        Args:
            customer_name: Name of the customer
            environment: Target environment
            artifacts: Collection of artifacts to deploy
            
        Returns:
            TerraformResult with apply results
            
        Raises:
            TerraformException: If apply fails
            
        Example:
            >>> wrapper = TerraformWrapper(Path("infrastructure"))
            >>> result = wrapper.apply("contoso", "dev", artifacts)
            >>> if result.success:
            ...     print(f"Deployed {len(result.outputs)} resources")
        """
        try:
            start_time = time.time()
            
            # Generate variables for this deployment
            tf_vars = self.generate_terraform_vars(customer_name, environment, artifacts)
            
            # Check if we have a plan file to use
            plan_file = self._get_plan_file_path(customer_name, environment)
            
            if plan_file.exists():
                # Apply using existing plan
                return_code, stdout, stderr = self.tf.apply(
                    str(plan_file),
                    capture_output=True,
                    auto_approve=IsNotFlagged
                )
            else:
                # Apply directly with variables
                return_code, stdout, stderr = self.tf.apply(
                    var=tf_vars,
                    capture_output=True,
                    auto_approve=IsFlagged
                )
            
            duration = time.time() - start_time
            success = return_code == 0
            
            # Get outputs if apply succeeded
            outputs = {}
            if success:
                try:
                    outputs = self.get_terraform_outputs(customer_name, environment)
                except Exception as e:
                    self.logger.warning(f"Failed to get Terraform outputs: {e}")
            
            result = TerraformResult(
                success=success,
                command="apply",
                exit_code=return_code,
                stdout=stdout,
                stderr=stderr,
                duration=duration,
                outputs=outputs
            )
            
            if not success:
                result.errors.append(f"Terraform apply failed: {stderr}")
            
            log_config_operation(
                self.logger, "TERRAFORM_APPLY",
                f"customer={customer_name}, environment={environment}, "
                f"success={success}, duration={duration:.2f}s, outputs={len(outputs)}"
            )
            
            return result
            
        except Exception as e:
            log_config_error(
                self.logger, "TERRAFORM_APPLY", e,
                f"customer={customer_name}, environment={environment}"
            )
            raise TerraformException(f"Terraform apply failed: {str(e)}")
    
    def destroy(self, customer_name: str, environment: str) -> TerraformResult:
        """
        Destroy Terraform-managed infrastructure.
        
        Args:
            customer_name: Name of the customer
            environment: Target environment
            
        Returns:
            TerraformResult with destroy results
            
        Raises:
            TerraformException: If destroy fails
            
        Example:
            >>> wrapper = TerraformWrapper(Path("infrastructure"))
            >>> result = wrapper.destroy("contoso", "dev")
            >>> if result.success:
            ...     print("Infrastructure destroyed successfully")
        """
        try:
            start_time = time.time()
            
            # Get basic variables (without artifacts since we're destroying)
            tf_vars = self._get_basic_terraform_vars(customer_name, environment)
            
            # Run terraform destroy
            return_code, stdout, stderr = self.tf.destroy(
                var=tf_vars,
                capture_output=True,
                auto_approve=IsFlagged
            )
            
            duration = time.time() - start_time
            success = return_code == 0
            
            result = TerraformResult(
                success=success,
                command="destroy",
                exit_code=return_code,
                stdout=stdout,
                stderr=stderr,
                duration=duration
            )
            
            if not success:
                result.errors.append(f"Terraform destroy failed: {stderr}")
            
            log_config_operation(
                self.logger, "TERRAFORM_DESTROY",
                f"customer={customer_name}, environment={environment}, "
                f"success={success}, duration={duration:.2f}s"
            )
            
            return result
            
        except Exception as e:
            log_config_error(
                self.logger, "TERRAFORM_DESTROY", e,
                f"customer={customer_name}, environment={environment}"
            )
            raise TerraformException(f"Terraform destroy failed: {str(e)}")
    
    def generate_terraform_vars(self, customer_name: str, environment: str, 
                               artifacts: ArtifactCollection) -> Dict[str, Any]:
        """
        Generate Terraform variables from customer config and artifacts.
        
        Args:
            customer_name: Name of the customer
            environment: Target environment
            artifacts: Collection of artifacts
            
        Returns:
            Dictionary of Terraform variables
            
        Example:
            >>> wrapper = TerraformWrapper(Path("infrastructure"))
            >>> vars = wrapper.generate_terraform_vars("contoso", "dev", artifacts)
            >>> print(vars["customer_name"])  # "contoso"
        """
        try:
            # Get basic variables
            tf_vars = self._get_basic_terraform_vars(customer_name, environment)
            
            # Add artifact-specific variables
            tf_vars.update({
                "notebook_count": len(artifacts.notebooks),
                "lakehouse_count": len(artifacts.lakehouses),
                "pipeline_count": len(artifacts.pipelines),
                "total_artifacts": artifacts.total_count,
                "artifact_paths": [str(path) for path in artifacts.all_artifacts]
            })
            
            return tf_vars
            
        except Exception as e:
            raise TerraformException(f"Failed to generate Terraform variables: {str(e)}")
    
    def save_terraform_plan(self, plan: TerraformPlan, output_dir: Path) -> Path:
        """
        Save Terraform plan to output directory for pipeline artifacts.
        
        Args:
            plan: Terraform plan to save
            output_dir: Directory to save plan artifacts
            
        Returns:
            Path to saved plan file
            
        Example:
            >>> wrapper = TerraformWrapper(Path("infrastructure"))
            >>> plan_path = wrapper.save_terraform_plan(plan, Path("outputs"))
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save plan file if it exists
            saved_plan_path = None
            if plan.plan_file and plan.plan_file.exists():
                saved_plan_path = output_dir / f"{plan.customer_name}-{plan.environment}.tfplan"
                saved_plan_path.write_bytes(plan.plan_file.read_bytes())
            
            # Save plan summary as JSON
            plan_summary = {
                "customer_name": plan.customer_name,
                "environment": plan.environment,
                "has_changes": plan.has_changes,
                "changes": plan.changes,
                "resources": plan.resources,
                "plan_file": str(saved_plan_path) if saved_plan_path else None
            }
            
            summary_path = output_dir / f"{plan.customer_name}-{plan.environment}-plan.json"
            with open(summary_path, 'w') as f:
                json.dump(plan_summary, f, indent=2)
            
            # Save plan output as text
            output_path = output_dir / f"{plan.customer_name}-{plan.environment}-plan.txt"
            output_path.write_text(plan.plan_output)
            
            log_config_operation(
                self.logger, "SAVE_PLAN",
                f"customer={plan.customer_name}, environment={plan.environment}, "
                f"output_dir={output_dir}"
            )
            
            return summary_path
            
        except Exception as e:
            raise TerraformException(f"Failed to save Terraform plan: {str(e)}")
    
    def get_terraform_outputs(self, customer_name: str, environment: str) -> Dict[str, Any]:
        """
        Get Terraform outputs for customer/environment.
        
        Args:
            customer_name: Name of the customer
            environment: Target environment
            
        Returns:
            Dictionary of Terraform outputs
            
        Example:
            >>> wrapper = TerraformWrapper(Path("infrastructure"))
            >>> outputs = wrapper.get_terraform_outputs("contoso", "dev")
            >>> print(outputs.get("workspace_id"))
        """
        try:
            return_code, stdout, stderr = self.tf.output(
                json=IsFlagged,
                capture_output=True
            )
            
            if return_code != 0:
                raise TerraformException(f"Failed to get outputs: {stderr}")
            
            if not stdout.strip():
                return {}
            
            outputs_raw = json.loads(stdout)
            
            # Extract values from Terraform output format
            outputs = {}
            for key, value_info in outputs_raw.items():
                outputs[key] = value_info.get("value")
            
            return outputs
            
        except json.JSONDecodeError as e:
            raise TerraformException(f"Failed to parse Terraform outputs: {str(e)}")
        except Exception as e:
            raise TerraformException(f"Failed to get Terraform outputs: {str(e)}")
    
    def get_terraform_state(self, customer_name: str, environment: str) -> Dict[str, Any]:
        """
        Get Terraform state information.
        
        Args:
            customer_name: Name of the customer
            environment: Target environment
            
        Returns:
            Dictionary with state information
        """
        try:
            return_code, stdout, stderr = self.tf.show(
                json=IsFlagged,
                capture_output=True
            )
            
            if return_code != 0:
                return {"exists": False, "error": stderr}
            
            if not stdout.strip():
                return {"exists": False}
            
            state_data = json.loads(stdout)
            
            return {
                "exists": True,
                "format_version": state_data.get("format_version"),
                "terraform_version": state_data.get("terraform_version"),
                "resource_count": len(state_data.get("values", {}).get("root_module", {}).get("resources", []))
            }
            
        except Exception as e:
            return {"exists": False, "error": str(e)}
    
    def validate_terraform_config(self) -> ValidationResult:
        """
        Validate Terraform configuration.
        
        Returns:
            ValidationResult with validation status
        """
        try:
            return_code, stdout, stderr = self.tf.validate(
                capture_output=True,
                json=IsFlagged
            )
            
            success = return_code == 0
            errors = []
            warnings = []
            
            if not success:
                errors.append(f"Terraform validation failed: {stderr}")
            
            if stdout:
                try:
                    validation_output = json.loads(stdout)
                    if validation_output.get("diagnostics"):
                        for diagnostic in validation_output["diagnostics"]:
                            severity = diagnostic.get("severity", "error")
                            summary = diagnostic.get("summary", "")
                            if severity == "error":
                                errors.append(summary)
                            elif severity == "warning":
                                warnings.append(summary)
                except json.JSONDecodeError:
                    pass
            
            return ValidationResult(
                success=success,
                errors=errors,
                warnings=warnings,
                checks_performed=["terraform_config_validation"]
            )
            
        except Exception as e:
            return ValidationResult(
                success=False,
                errors=[f"Terraform validation error: {str(e)}"],
                checks_performed=["terraform_config_validation"]
            )
    
    def _check_terraform_available(self) -> bool:
        """Check if Terraform executable is available."""
        try:
            result = subprocess.run(
                ["terraform", "version"],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _get_backend_config(self, customer_name: str, environment: str) -> Dict[str, str]:
        """Get backend configuration for customer/environment."""
        if self.state_backend == "azurerm":
            return {
                "resource_group_name": os.getenv("TF_BACKEND_RESOURCE_GROUP", "terraform-state"),
                "storage_account_name": os.getenv("TF_BACKEND_STORAGE_ACCOUNT", "terraformstate"),
                "container_name": os.getenv("TF_BACKEND_CONTAINER", "tfstate"),
                "key": f"{customer_name}/{environment}/terraform.tfstate"
            }
        elif self.state_backend == "s3":
            return {
                "bucket": os.getenv("TF_BACKEND_BUCKET", "terraform-state"),
                "key": f"{customer_name}/{environment}/terraform.tfstate",
                "region": os.getenv("TF_BACKEND_REGION", "us-east-1")
            }
        else:
            # Local backend
            return {}
    
    def _get_plan_file_path(self, customer_name: str, environment: str) -> Path:
        """Get path for Terraform plan file."""
        return self.terraform_dir / f"{customer_name}-{environment}.tfplan"
    
    def _get_basic_terraform_vars(self, customer_name: str, environment: str) -> Dict[str, Any]:
        """Get basic Terraform variables for customer/environment."""
        return {
            "customer_name": customer_name,
            "environment": environment,
            "deployment_timestamp": int(time.time())
        }
    
    def _parse_plan_output(self, plan_output: str) -> Dict[str, int]:
        """Parse Terraform plan output to extract change counts."""
        changes = {"add": 0, "change": 0, "destroy": 0}
        
        # Look for plan summary line like "Plan: 3 to add, 1 to change, 0 to destroy."
        import re
        plan_pattern = r"Plan: (\d+) to add, (\d+) to change, (\d+) to destroy"
        match = re.search(plan_pattern, plan_output)
        
        if match:
            changes["add"] = int(match.group(1))
            changes["change"] = int(match.group(2))
            changes["destroy"] = int(match.group(3))
        
        return changes
    
    def _extract_resources_from_plan(self, plan_output: str) -> List[str]:
        """Extract resource names from Terraform plan output."""
        resources = []
        
        # Look for resource creation/modification lines
        import re
        resource_pattern = r"[#~+-] ([a-zA-Z0-9_\[\]\.]+)"
        matches = re.findall(resource_pattern, plan_output)
        
        resources.extend(matches)
        
        return list(set(resources))  # Remove duplicates