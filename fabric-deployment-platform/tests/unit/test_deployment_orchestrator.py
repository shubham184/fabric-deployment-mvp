"""
Unit tests for the DeploymentOrchestrator class.

This module tests the main deployment orchestration functionality including
single customer deployment, batch deployment, planning, and validation.
"""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from src.config.loader import ConfigLoader
from src.deployment.artifact_manager import ArtifactManager
from src.deployment.models import (
    ArtifactCollection, BatchDeploymentResult, DeploymentPlan, DeploymentResult,
    DeploymentStatus, PhaseResults, PrerequisiteCheck, TerraformPlan, ValidationResult
)
from src.deployment.orchestrator import DeploymentOrchestrator
from src.deployment.terraform_wrapper import TerraformWrapper
from src.deployment.validator import DeploymentValidator


class TestDeploymentOrchestrator(unittest.TestCase):
    """Test cases for DeploymentOrchestrator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        
        # Create mock directories
        self.notebooks_dir = self.temp_path / "notebooks"
        self.output_dir = self.temp_path / "outputs"
        self.notebooks_dir.mkdir()
        self.output_dir.mkdir()
        
        # Create mock dependencies
        self.mock_config_loader = Mock(spec=ConfigLoader)
        self.mock_terraform_wrapper = Mock(spec=TerraformWrapper)
        
        # Initialize orchestrator
        self.orchestrator = DeploymentOrchestrator(
            config_loader=self.mock_config_loader,
            terraform_wrapper=self.mock_terraform_wrapper,
            notebooks_dir=self.notebooks_dir,
            output_dir=self.output_dir
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        self.assertIsInstance(self.orchestrator.config_loader, Mock)
        self.assertIsInstance(self.orchestrator.terraform_wrapper, Mock)
        self.assertIsInstance(self.orchestrator.artifact_manager, ArtifactManager)
        self.assertIsInstance(self.orchestrator.validator, DeploymentValidator)
        self.assertEqual(self.orchestrator.output_dir, self.output_dir)
    
    def test_deploy_customer_success(self):
        """Test successful customer deployment."""
        # Mock successful validation
        mock_validation = ValidationResult(success=True)
        self.orchestrator.validate_deployment_readiness = Mock(return_value=mock_validation)
        
        # Mock successful planning
        mock_plan = DeploymentPlan(
            customer_name="test-customer",
            environment="dev",
            artifacts=ArtifactCollection("test-customer", "dev"),
            terraform_plan=TerraformPlan("test-customer", "dev"),
            validation_result=ValidationResult(success=True)
        )
        self.orchestrator.plan_deployment = Mock(return_value=mock_plan)
        
        # Mock successful phase execution
        mock_phase_results = PhaseResults()
        mock_phase_results.infrastructure = Mock(success=True)
        mock_phase_results.artifacts = Mock(success=True)
        self.orchestrator._execute_deployment_phases = Mock(return_value=mock_phase_results)
        
        # Mock verification
        self.orchestrator._verify_deployment = Mock(return_value=True)
        
        # Mock Terraform outputs
        self.mock_terraform_wrapper.get_terraform_outputs.return_value = {
            "workspace_id": "test-workspace-123"
        }
        
        # Execute deployment
        result = self.orchestrator.deploy_customer("test-customer", "dev")
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.customer_name, "test-customer")
        self.assertEqual(result.environment, "dev")
        self.assertEqual(result.status, DeploymentStatus.DEPLOYED)
        self.assertEqual(result.workspace_id, "test-workspace-123")
        self.assertGreater(result.deployment_time, 0)
    
    def test_deploy_customer_validation_failure(self):
        """Test customer deployment with validation failure."""
        # Mock validation failure
        mock_validation = ValidationResult(
            success=False,
            errors=["Configuration invalid", "Missing artifacts"]
        )
        self.orchestrator.validate_deployment_readiness = Mock(return_value=mock_validation)
        
        # Execute deployment
        result = self.orchestrator.deploy_customer("test-customer", "dev")
        
        # Verify result
        self.assertFalse(result.success)
        self.assertEqual(result.status, DeploymentStatus.FAILED)
        self.assertIn("Validation failed", result.errors[0])
    
    def test_deploy_customer_dry_run(self):
        """Test customer deployment in dry run mode."""
        # Mock successful validation and planning
        mock_validation = ValidationResult(success=True)
        self.orchestrator.validate_deployment_readiness = Mock(return_value=mock_validation)
        
        mock_plan = DeploymentPlan(
            customer_name="test-customer",
            environment="dev",
            artifacts=ArtifactCollection("test-customer", "dev"),
            terraform_plan=TerraformPlan("test-customer", "dev"),
            validation_result=ValidationResult(success=True)
        )
        self.orchestrator.plan_deployment = Mock(return_value=mock_plan)
        
        # Execute dry run
        result = self.orchestrator.deploy_customer("test-customer", "dev", dry_run=True)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.status, DeploymentStatus.DEPLOYED)
        
        # Verify deployment phases were not executed
        self.orchestrator._execute_deployment_phases.assert_not_called()
    
    def test_deploy_multiple_customers_sequential(self):
        """Test sequential deployment of multiple customers."""
        customers = ["customer1", "customer2", "customer3"]
        
        # Mock individual deployments
        def mock_deploy_customer(customer_name, environment, dry_run=False):
            return DeploymentResult(
                customer_name=customer_name,
                environment=environment,
                status=DeploymentStatus.DEPLOYED,
                success=True,
                deployment_time=1.0,
                started_at=datetime.now(),
                completed_at=datetime.now()
            )
        
        self.orchestrator.deploy_customer = Mock(side_effect=mock_deploy_customer)
        
        # Execute batch deployment
        result = self.orchestrator.deploy_multiple_customers(
            customers, "dev", parallel=False, continue_on_error=False
        )
        
        # Verify result
        self.assertEqual(result.total_customers, 3)
        self.assertEqual(result.success_count, 3)
        self.assertEqual(result.failure_count, 0)
        self.assertTrue(result.overall_success)
        
        # Verify individual deployments were called
        self.assertEqual(self.orchestrator.deploy_customer.call_count, 3)
    
    def test_deploy_multiple_customers_with_failure(self):
        """Test batch deployment with one customer failure."""
        customers = ["customer1", "customer2", "customer3"]
        
        # Mock deployments with one failure
        def mock_deploy_customer(customer_name, environment, dry_run=False):
            if customer_name == "customer2":
                result = DeploymentResult(
                    customer_name=customer_name,
                    environment=environment,
                    status=DeploymentStatus.FAILED,
                    success=False
                )
                result.add_error("Deployment failed")
                return result
            else:
                return DeploymentResult(
                    customer_name=customer_name,
                    environment=environment,
                    status=DeploymentStatus.DEPLOYED,
                    success=True
                )
        
        self.orchestrator.deploy_customer = Mock(side_effect=mock_deploy_customer)
        
        # Execute batch deployment with continue on error
        result = self.orchestrator.deploy_multiple_customers(
            customers, "dev", parallel=False, continue_on_error=True
        )
        
        # Verify result
        self.assertEqual(result.total_customers, 3)
        self.assertEqual(result.success_count, 2)
        self.assertEqual(result.failure_count, 1)
        self.assertFalse(result.overall_success)
        
        # Verify all deployments were attempted
        self.assertEqual(self.orchestrator.deploy_customer.call_count, 3)
    
    def test_plan_deployment(self):
        """Test deployment planning."""
        # Mock artifact discovery
        mock_artifacts = ArtifactCollection("test-customer", "dev")
        self.orchestrator._discover_artifacts = Mock(return_value=mock_artifacts)
        
        # Mock prerequisite validation
        mock_prereqs = PrerequisiteCheck()
        mock_prereqs.terraform_available = True
        mock_prereqs.configuration_valid = True
        mock_prereqs.artifacts_present = True
        mock_prereqs.workspace_accessible = True
        mock_prereqs.credentials_valid = True
        self.orchestrator._validate_prerequisites = Mock(return_value=mock_prereqs)
        
        # Mock Terraform plan
        mock_tf_plan = TerraformPlan("test-customer", "dev", has_changes=True)
        mock_tf_plan.changes = {"add": 3, "change": 1, "destroy": 0}
        self.mock_terraform_wrapper.plan.return_value = mock_tf_plan
        
        # Execute planning
        plan = self.orchestrator.plan_deployment("test-customer", "dev")
        
        # Verify plan
        self.assertEqual(plan.customer_name, "test-customer")
        self.assertEqual(plan.environment, "dev")
        self.assertEqual(plan.artifacts, mock_artifacts)
        self.assertEqual(plan.terraform_plan, mock_tf_plan)
        self.assertTrue(plan.validation_result.success)
        self.assertGreater(plan.estimated_duration, 0)
    
    def test_plan_deployment_with_prerequisite_failure(self):
        """Test deployment planning with prerequisite failure."""
        # Mock artifact discovery
        mock_artifacts = ArtifactCollection("test-customer", "dev")
        self.orchestrator._discover_artifacts = Mock(return_value=mock_artifacts)
        
        # Mock prerequisite failure
        mock_prereqs = PrerequisiteCheck()
        mock_prereqs.terraform_available = False
        mock_prereqs.configuration_valid = True
        mock_prereqs.artifacts_present = True
        mock_prereqs.workspace_accessible = True
        mock_prereqs.credentials_valid = True
        self.orchestrator._validate_prerequisites = Mock(return_value=mock_prereqs)
        
        # Mock Terraform plan
        mock_tf_plan = TerraformPlan("test-customer", "dev")
        self.mock_terraform_wrapper.plan.return_value = mock_tf_plan
        
        # Execute planning
        plan = self.orchestrator.plan_deployment("test-customer", "dev")
        
        # Verify plan has validation failure
        self.assertFalse(plan.validation_result.success)
        self.assertIn("Prerequisites not met", plan.validation_result.errors[0])
        self.assertIn("terraform_available", plan.prerequisite_checks)
    
    def test_destroy_deployment_success(self):
        """Test successful deployment destruction."""
        # Mock successful Terraform destroy
        mock_tf_result = Mock()
        mock_tf_result.success = True
        mock_tf_result.errors = []
        self.mock_terraform_wrapper.destroy.return_value = mock_tf_result
        
        # Execute destroy
        result = self.orchestrator.destroy_deployment("test-customer", "dev")
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.customer_name, "test-customer")
        self.assertEqual(result.environment, "dev")
        self.assertEqual(result.status, DeploymentStatus.NOT_DEPLOYED)
        self.assertGreater(result.deployment_time, 0)
    
    def test_destroy_deployment_failure(self):
        """Test deployment destruction failure."""
        # Mock failed Terraform destroy
        mock_tf_result = Mock()
        mock_tf_result.success = False
        mock_tf_result.errors = ["Terraform destroy failed"]
        self.mock_terraform_wrapper.destroy.return_value = mock_tf_result
        
        # Execute destroy
        result = self.orchestrator.destroy_deployment("test-customer", "dev")
        
        # Verify result
        self.assertFalse(result.success)
        self.assertEqual(result.status, DeploymentStatus.FAILED)
        self.assertIn("Terraform destroy failed", result.errors)
    
    def test_validate_deployment_readiness(self):
        """Test deployment readiness validation."""
        # Mock successful validation
        mock_validation = ValidationResult(
            success=True,
            warnings=["Minor configuration warning"],
            checks_performed=["config_validation", "artifact_validation"]
        )
        self.orchestrator.validator.validate_deployment_readiness = Mock(return_value=mock_validation)
        
        # Execute validation
        result = self.orchestrator.validate_deployment_readiness("test-customer", "dev")
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(len(result.checks_performed), 2)
    
    def test_get_deployment_status_deployed(self):
        """Test getting deployment status for deployed customer."""
        # Mock Terraform state indicating deployment exists
        mock_state = {"exists": True, "resource_count": 5}
        self.mock_terraform_wrapper.get_terraform_state.return_value = mock_state
        
        # Get status
        status = self.orchestrator.get_deployment_status("test-customer", "dev")
        
        # Verify status
        self.assertEqual(status, DeploymentStatus.DEPLOYED)
    
    def test_get_deployment_status_not_deployed(self):
        """Test getting deployment status for non-deployed customer."""
        # Mock Terraform state indicating no deployment
        mock_state = {"exists": False}
        self.mock_terraform_wrapper.get_terraform_state.return_value = mock_state
        
        # Get status
        status = self.orchestrator.get_deployment_status("test-customer", "dev")
        
        # Verify status
        self.assertEqual(status, DeploymentStatus.NOT_DEPLOYED)
    
    def test_estimate_deployment_duration(self):
        """Test deployment duration estimation."""
        # Create artifacts collection
        artifacts = ArtifactCollection("test-customer", "dev")
        artifacts.notebooks = [Path("notebook1.ipynb"), Path("notebook2.ipynb")]
        artifacts.lakehouses = [Path("lakehouse1.json")]
        
        # Estimate duration
        duration = self.orchestrator._estimate_deployment_duration(artifacts)
        
        # Verify estimation
        expected_duration = 60.0 + (3 * 30.0)  # Base + (3 artifacts * 30s each)
        self.assertEqual(duration, expected_duration)
    
    @patch('src.deployment.orchestrator.ThreadPoolExecutor')
    def test_parallel_deployment(self, mock_executor):
        """Test parallel customer deployment."""
        customers = ["customer1", "customer2"]
        
        # Mock thread pool executor
        mock_future1 = Mock()
        mock_future1.result.return_value = DeploymentResult(
            customer_name="customer1", environment="dev", 
            status=DeploymentStatus.DEPLOYED, success=True
        )
        
        mock_future2 = Mock()
        mock_future2.result.return_value = DeploymentResult(
            customer_name="customer2", environment="dev",
            status=DeploymentStatus.DEPLOYED, success=True
        )
        
        mock_executor_instance = Mock()
        mock_executor_instance.submit.side_effect = [mock_future1, mock_future2]
        mock_executor_instance.__enter__.return_value = mock_executor_instance
        mock_executor_instance.__exit__.return_value = None
        mock_executor.return_value = mock_executor_instance
        
        # Mock as_completed to return futures in order
        with patch('src.deployment.orchestrator.as_completed', return_value=[mock_future1, mock_future2]):
            # Execute parallel deployment
            result = self.orchestrator.deploy_multiple_customers(
                customers, "dev", parallel=True, continue_on_error=False
            )
        
        # Verify parallel execution was used
        mock_executor.assert_called_once()
        self.assertEqual(result.success_count, 2)
        self.assertEqual(result.failure_count, 0)


class TestDeploymentOrchestratorIntegration(unittest.TestCase):
    """Integration tests for DeploymentOrchestrator."""
    
    def test_end_to_end_deployment_flow(self):
        """Test complete deployment flow with all components."""
        # This would be an integration test with real components
        # For now, we'll skip this as it requires full setup
        pass


if __name__ == "__main__":
    unittest.main()