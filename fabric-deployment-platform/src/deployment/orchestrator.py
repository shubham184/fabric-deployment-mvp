"""
Main deployment orchestrator for Microsoft Fabric platform.

This module provides the DeploymentOrchestrator class that coordinates
the entire deployment process, from validation through Terraform
deployment to post-deployment verification.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import List

from .artifact_manager import ArtifactManager
from .models import (
    ArtifactCollection, BatchDeploymentResult, DeploymentPlan, DeploymentResult,
    DeploymentStatus, PhaseResults, PrerequisiteCheck, ValidationResult,
    DeploymentPhase, DeploymentException, ValidationException, TerraformException
)
from .terraform_wrapper import TerraformWrapper
from .validator import DeploymentValidator
from ..config.loader import ConfigLoader
from ..utils.logger import get_logger, log_config_operation, log_config_error


class DeploymentOrchestrator:
    """
    Main orchestrator for Microsoft Fabric deployments.
    
    This class coordinates the entire deployment process including
    validation, planning, infrastructure deployment, artifact deployment,
    and verification. Supports both single customer and batch deployments
    with full Azure DevOps pipeline integration.
    """
    
    def __init__(self, config_loader: ConfigLoader, terraform_wrapper: TerraformWrapper,
                 notebooks_dir: Path, output_dir: Optional[Path] = None):
        """
        Initialize deployment orchestrator.
        
        Args:
            config_loader: Configuration loader instance
            terraform_wrapper: Terraform wrapper instance
            notebooks_dir: Directory containing generated notebooks
            output_dir: Directory for deployment outputs (optional)
            
        Example:
            >>> config_loader = ConfigLoader(Path("configs"), Path("schemas"))
            >>> tf_wrapper = TerraformWrapper(Path("infrastructure"))
            >>> orchestrator = DeploymentOrchestrator(
            ...     config_loader, tf_wrapper, Path("generated-notebooks")
            ... )
        """
        self.config_loader = config_loader
        self.terraform_wrapper = terraform_wrapper
        self.artifact_manager = ArtifactManager(notebooks_dir, config_loader)
        self.validator = DeploymentValidator(config_loader.schemas_dir)
        self.output_dir = output_dir or Path("./deployment-outputs")
        self.logger = get_logger(__name__)
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        log_config_operation(
            self.logger, "INIT_ORCHESTRATOR",
            f"notebooks_dir={notebooks_dir}, output_dir={self.output_dir}"
        )
    
    def deploy_customer(self, customer_name: str, environment: str, 
                       dry_run: bool = False) -> DeploymentResult:
        """
        Deploy single customer to specified environment.
        
        Args:
            customer_name: Name of the customer to deploy
            environment: Target environment (dev, test, prod)
            dry_run: If True, only plan deployment without applying
            
        Returns:
            DeploymentResult with deployment outcome
            
        Raises:
            DeploymentException: If deployment fails
            
        Example:
            >>> orchestrator = DeploymentOrchestrator(config_loader, tf_wrapper, notebooks_dir)
            >>> result = orchestrator.deploy_customer("contoso", "dev")
            >>> if result.success:
            ...     print(f"Deployed {len(result.artifacts_deployed)} artifacts")
        """
        start_time = time.time()
        started_at = datetime.now()
        
        result = DeploymentResult(
            customer_name=customer_name,
            environment=environment,
            status=DeploymentStatus.DEPLOYING,
            success=False,
            started_at=started_at
        )
        
        try:
            log_config_operation(
                self.logger, "START_DEPLOYMENT",
                f"customer={customer_name}, environment={environment}, dry_run={dry_run}"
            )
            
            # Phase 1: Validation
            self.logger.info("Phase 1: Validating deployment readiness...")
            validation_result = self.validate_deployment_readiness(customer_name, environment)
            if not validation_result.success:
                result.add_error(f"Validation failed: {'; '.join(validation_result.errors)}")
                return result
            
            result.phases_completed.append(DeploymentPhase.VALIDATION)
            
            # Phase 2: Planning
            self.logger.info("Phase 2: Creating deployment plan...")
            deployment_plan = self.plan_deployment(customer_name, environment)
            if not deployment_plan.validation_result.success:
                result.add_error(f"Planning failed: {'; '.join(deployment_plan.validation_result.errors)}")
                return result
            
            result.phases_completed.append(DeploymentPhase.PLANNING)
            
            # If dry run, stop here
            if dry_run:
                result.success = True
                result.status = DeploymentStatus.DEPLOYED
                result.deployment_time = time.time() - start_time
                result.completed_at = datetime.now()
                
                self.logger.info(f"Dry run completed successfully for {customer_name}/{environment}")
                return result
            
            # Phase 3: Infrastructure Deployment
            self.logger.info("Phase 3: Deploying infrastructure...")
            phase_results = self._execute_deployment_phases(
                deployment_plan.artifacts, 
                self.config_loader.load_merged_config(customer_name, environment)
            )
            
            if not phase_results.all_successful:
                result.add_error("Infrastructure deployment failed")
                return result
            
            result.phases_completed.append(DeploymentPhase.INFRASTRUCTURE)
            result.phases_completed.append(DeploymentPhase.ARTIFACTS)
            
            # Phase 4: Verification
            self.logger.info("Phase 4: Verifying deployment...")
            verification_result = self._verify_deployment(customer_name, environment)
            if verification_result:
                result.phases_completed.append(DeploymentPhase.VERIFICATION)
            
            # Success!
            result.success = True
            result.status = DeploymentStatus.DEPLOYED
            result.deployment_time = time.time() - start_time
            result.completed_at = datetime.now()
            
            # Get deployment outputs
            try:
                result.terraform_outputs = self.terraform_wrapper.get_terraform_outputs(
                    customer_name, environment
                )
                result.workspace_id = result.terraform_outputs.get("workspace_id", "")
            except Exception as e:
                result.add_warning(f"Failed to get Terraform outputs: {str(e)}")
            
            # Set deployed artifacts
            result.artifacts_deployed = [
                str(artifact) for artifact in deployment_plan.artifacts.all_artifacts
            ]
            
            log_config_operation(
                self.logger, "DEPLOYMENT_SUCCESS",
                f"customer={customer_name}, environment={environment}, "
                f"duration={result.deployment_time:.2f}s, artifacts={len(result.artifacts_deployed)}"
            )
            
            return result
            
        except Exception as e:
            result.add_error(str(e))
            result.deployment_time = time.time() - start_time
            result.completed_at = datetime.now()
            
            log_config_error(
                self.logger, "DEPLOYMENT_FAILED", e,
                f"customer={customer_name}, environment={environment}"
            )
            
            return result
    
    def deploy_multiple_customers(self, customers: List[str], environment: str,
                                 parallel: bool = False, continue_on_error: bool = False) -> BatchDeploymentResult:
        """
        Deploy multiple customers to the same environment.
        
        Args:
            customers: List of customer names to deploy
            environment: Target environment
            parallel: Whether to deploy customers in parallel
            continue_on_error: Whether to continue if one customer fails
            
        Returns:
            BatchDeploymentResult with all deployment outcomes
            
        Example:
            >>> customers = ["contoso", "fabrikam", "northwind"]
            >>> result = orchestrator.deploy_multiple_customers(customers, "dev", parallel=True)
            >>> print(f"Success: {result.success_count}/{result.total_customers}")
        """
        started_at = datetime.now()
        
        batch_result = BatchDeploymentResult(
            environment=environment,
            total_customers=len(customers),
            started_at=started_at
        )
        
        try:
            log_config_operation(
                self.logger, "START_BATCH_DEPLOYMENT",
                f"customers={customers}, environment={environment}, "
                f"parallel={parallel}, continue_on_error={continue_on_error}"
            )
            
            if parallel:
                self._deploy_customers_parallel(customers, environment, batch_result, continue_on_error)
            else:
                self._deploy_customers_sequential(customers, environment, batch_result, continue_on_error)
            
            batch_result.completed_at = datetime.now()
            
            log_config_operation(
                self.logger, "BATCH_DEPLOYMENT_COMPLETE",
                f"environment={environment}, success={batch_result.success_count}, "
                f"failed={batch_result.failure_count}, total={batch_result.total_customers}"
            )
            
            return batch_result
            
        except Exception as e:
            log_config_error(
                self.logger, "BATCH_DEPLOYMENT_FAILED", e,
                f"customers={customers}, environment={environment}"
            )
            batch_result.completed_at = datetime.now()
            return batch_result
    
    def plan_deployment(self, customer_name: str, environment: str) -> DeploymentPlan:
        """
        Create deployment plan without executing.
        
        Args:
            customer_name: Name of the customer
            environment: Target environment
            
        Returns:
            DeploymentPlan with planned deployment details
            
        Raises:
            DeploymentException: If planning fails
            
        Example:
            >>> plan = orchestrator.plan_deployment("contoso", "dev")
            >>> print(f"Plan will deploy {plan.artifacts.total_count} artifacts")
        """
        try:
            log_config_operation(
                self.logger, "START_PLANNING",
                f"customer={customer_name}, environment={environment}"
            )
            
            # Discover artifacts
            artifacts = self._discover_artifacts(customer_name, environment)
            
            # Validate prerequisites
            prereq_check = self._validate_prerequisites(customer_name, environment)
            if not prereq_check.all_met:
                validation_result = ValidationResult(
                    success=False,
                    errors=[f"Prerequisites not met: {', '.join(prereq_check.failed_checks)}"]
                )
            else:
                validation_result = ValidationResult(success=True)
            
            # Create Terraform plan
            terraform_plan = self.terraform_wrapper.plan(customer_name, environment, artifacts)
            
            plan = DeploymentPlan(
                customer_name=customer_name,
                environment=environment,
                artifacts=artifacts,
                terraform_plan=terraform_plan,
                validation_result=validation_result,
                estimated_duration=self._estimate_deployment_duration(artifacts),
                prerequisite_checks=prereq_check.failed_checks
            )
            
            log_config_operation(
                self.logger, "PLANNING_COMPLETE",
                f"customer={customer_name}, environment={environment}, "
                f"artifacts={artifacts.total_count}, has_changes={terraform_plan.has_changes}"
            )
            
            return plan
            
        except Exception as e:
            log_config_error(
                self.logger, "PLANNING_FAILED", e,
                f"customer={customer_name}, environment={environment}"
            )
            raise DeploymentException(f"Planning failed: {str(e)}")
    
    def destroy_deployment(self, customer_name: str, environment: str) -> DeploymentResult:
        """
        Destroy customer deployment.
        
        Args:
            customer_name: Name of the customer
            environment: Target environment
            
        Returns:
            DeploymentResult with destruction outcome
            
        Example:
            >>> result = orchestrator.destroy_deployment("contoso", "dev")
            >>> if result.success:
            ...     print("Infrastructure destroyed successfully")
        """
        start_time = time.time()
        
        result = DeploymentResult(
            customer_name=customer_name,
            environment=environment,
            status=DeploymentStatus.DESTROYING,
            success=False,
            started_at=datetime.now()
        )
        
        try:
            log_config_operation(
                self.logger, "START_DESTROY",
                f"customer={customer_name}, environment={environment}"
            )
            
            # Run Terraform destroy
            tf_result = self.terraform_wrapper.destroy(customer_name, environment)
            
            result.success = tf_result.success
            result.status = DeploymentStatus.NOT_DEPLOYED if tf_result.success else DeploymentStatus.FAILED
            result.deployment_time = time.time() - start_time
            result.completed_at = datetime.now()
            
            if not tf_result.success:
                result.errors.extend(tf_result.errors)
            
            log_config_operation(
                self.logger, "DESTROY_COMPLETE",
                f"customer={customer_name}, environment={environment}, "
                f"success={result.success}, duration={result.deployment_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            result.add_error(str(e))
            result.deployment_time = time.time() - start_time
            result.completed_at = datetime.now()
            
            log_config_error(
                self.logger, "DESTROY_FAILED", e,
                f"customer={customer_name}, environment={environment}"
            )
            
            return result
    
    def validate_deployment_readiness(self, customer_name: str, environment: str) -> ValidationResult:
        """
        Validate deployment readiness for customer/environment.
        
        Args:
            customer_name: Name of the customer
            environment: Target environment
            
        Returns:
            ValidationResult with validation status
            
        Example:
            >>> validation = orchestrator.validate_deployment_readiness("contoso", "dev")
            >>> if not validation.success:
            ...     print(f"Validation errors: {validation.errors}")
        """
        try:
            return self.validator.validate_deployment_readiness(customer_name, environment)
        except Exception as e:
            return ValidationResult(
                success=False,
                errors=[f"Validation failed: {str(e)}"]
            )
    
    def get_deployment_status(self, customer_name: str, environment: str) -> DeploymentStatus:
        """
        Get current deployment status for customer/environment.
        
        Args:
            customer_name: Name of the customer
            environment: Target environment
            
        Returns:
            DeploymentStatus enum value
            
        Example:
            >>> status = orchestrator.get_deployment_status("contoso", "dev")
            >>> print(f"Status: {status.value}")
        """
        try:
            # Check Terraform state to determine status
            state_info = self.terraform_wrapper.get_terraform_state(customer_name, environment)
            
            if not state_info.get("exists", False):
                return DeploymentStatus.NOT_DEPLOYED
            
            # If state exists and has resources, consider it deployed
            if state_info.get("resource_count", 0) > 0:
                return DeploymentStatus.DEPLOYED
            
            return DeploymentStatus.NOT_DEPLOYED
            
        except Exception as e:
            self.logger.warning(f"Failed to get deployment status: {e}")
            return DeploymentStatus.NOT_DEPLOYED
    
    def _discover_artifacts(self, customer_name: str, environment: str) -> ArtifactCollection:
        """Discover artifacts for customer/environment."""
        return self.artifact_manager.discover_customer_artifacts(customer_name, environment)
    
    def _validate_prerequisites(self, customer_name: str, environment: str) -> PrerequisiteCheck:
        """Validate deployment prerequisites."""
        return self.validator.validate_prerequisites(customer_name, environment)
    
    def _execute_deployment_phases(self, artifacts: ArtifactCollection, config: dict) -> PhaseResults:
        """Execute main deployment phases."""
        phase_results = PhaseResults()
        
        try:
            # Initialize Terraform
            init_result = self.terraform_wrapper.init(artifacts.customer_name, artifacts.environment)
            if not init_result.success:
                phase_results.infrastructure = init_result
                return phase_results
            
            # Apply Terraform configuration
            apply_result = self.terraform_wrapper.apply(
                artifacts.customer_name, artifacts.environment, artifacts
            )
            phase_results.infrastructure = apply_result
            phase_results.artifacts = apply_result  # Same result for both phases
            
            return phase_results
            
        except Exception as e:
            self.logger.error(f"Deployment phase execution failed: {e}")
            return phase_results
    
    def _verify_deployment(self, customer_name: str, environment: str) -> bool:
        """Verify deployment completed successfully."""
        try:
            # Basic verification - check if Terraform outputs are available
            outputs = self.terraform_wrapper.get_terraform_outputs(customer_name, environment)
            return len(outputs) > 0
        except Exception as e:
            self.logger.warning(f"Deployment verification failed: {e}")
            return False
    
    def _deploy_customers_parallel(self, customers: List[str], environment: str,
                                  batch_result: BatchDeploymentResult, continue_on_error: bool):
        """Deploy customers in parallel."""
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit deployment tasks
            future_to_customer = {
                executor.submit(self.deploy_customer, customer, environment): customer
                for customer in customers
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_customer):
                customer = future_to_customer[future]
                try:
                    result = future.result()
                    if result.success:
                        batch_result.successful_deployments.append(result)
                    else:
                        batch_result.failed_deployments.append(result)
                        if not continue_on_error:
                            # Cancel remaining deployments
                            for remaining_future in future_to_customer:
                                if not remaining_future.done():
                                    remaining_future.cancel()
                            break
                except Exception as e:
                    # Create failed result for exception
                    failed_result = DeploymentResult(
                        customer_name=customer,
                        environment=environment,
                        status=DeploymentStatus.FAILED,
                        success=False
                    )
                    failed_result.add_error(str(e))
                    batch_result.failed_deployments.append(failed_result)
    
    def _deploy_customers_sequential(self, customers: List[str], environment: str,
                                   batch_result: BatchDeploymentResult, continue_on_error: bool):
        """Deploy customers sequentially."""
        for customer in customers:
            try:
                result = self.deploy_customer(customer, environment)
                if result.success:
                    batch_result.successful_deployments.append(result)
                else:
                    batch_result.failed_deployments.append(result)
                    if not continue_on_error:
                        break
            except Exception as e:
                failed_result = DeploymentResult(
                    customer_name=customer,
                    environment=environment,
                    status=DeploymentStatus.FAILED,
                    success=False
                )
                failed_result.add_error(str(e))
                batch_result.failed_deployments.append(failed_result)
                
                if not continue_on_error:
                    break
    
    def _estimate_deployment_duration(self, artifacts: ArtifactCollection) -> float:
        """Estimate deployment duration in seconds."""
        # Simple estimation based on artifact count
        base_time = 60.0  # Base 1 minute
        per_artifact_time = 30.0  # 30 seconds per artifact
        return base_time + (artifacts.total_count * per_artifact_time)