"""
Artifact discovery and management for Microsoft Fabric deployment.

This module provides the ArtifactManager class that discovers generated
notebooks and other artifacts, validates their existence and content,
and prepares them for Terraform deployment.
"""

import json
from pathlib import Path
from typing import Dict, List

from .models import (
    ArtifactCollection, ArtifactValidation, ContentValidation, 
    DeploymentOrder, TerraformArtifacts, ArtifactException
)
from ..config.loader import ConfigLoader
from ..utils.helpers import safe_load_yaml, validate_file_exists
from ..utils.logger import get_logger, log_config_operation, log_config_error


class ArtifactManager:
    """
    Manages artifact discovery and preparation for deployment.
    
    This class handles discovering generated notebooks and other artifacts,
    validating their existence and content, organizing them by deployment
    phase, and preparing them for Terraform deployment.
    """
    
    def __init__(self, notebooks_dir: Path, config_loader: ConfigLoader):
        """
        Initialize artifact manager.
        
        Args:
            notebooks_dir: Directory containing generated notebook files
            config_loader: Configuration loader instance
            
        Raises:
            FileNotFoundError: If notebooks directory doesn't exist
        """
        self.notebooks_dir = Path(notebooks_dir)
        self.config_loader = config_loader
        self.logger = get_logger(__name__)
        
        if not self.notebooks_dir.exists():
            raise FileNotFoundError(f"Notebooks directory not found: {self.notebooks_dir}")
        
        log_config_operation(
            self.logger, "INIT_ARTIFACTS", 
            f"notebooks_dir={self.notebooks_dir}"
        )
    
    def discover_customer_artifacts(self, customer_name: str, environment: str) -> ArtifactCollection:
        """
        Discover all artifacts for a customer and environment.
        
        Args:
            customer_name: Name of the customer
            environment: Target environment (dev, test, prod)
            
        Returns:
            ArtifactCollection containing discovered artifacts
            
        Raises:
            ArtifactException: If artifact discovery fails
            
        Example:
            >>> manager = ArtifactManager(Path("predefined-artifacts"), config_loader)
            >>> artifacts = manager.discover_customer_artifacts("contoso", "dev")
            >>> print(f"Found {artifacts.total_count} artifacts")
        """
        try:
            customer_dir = self.notebooks_dir / customer_name / environment
            
            if not customer_dir.exists():
                raise ArtifactException(f"Customer artifacts directory not found: {customer_dir}")
            
            # Look in notebooks subdirectory if it exists
            notebooks_dir = customer_dir / "notebooks"
            search_dir = notebooks_dir if notebooks_dir.exists() else customer_dir
            
            # Discover ONLY notebooks (.ipynb files)
            all_notebooks = []
            for pattern in ["*.ipynb", "bronze-*.ipynb", "silver-*.ipynb", "gold-*.ipynb"]:
                notebooks = self._discover_artifacts_by_pattern(search_dir, pattern)
                all_notebooks.extend(notebooks)
            
            # Remove duplicates
            all_notebooks = list(set(all_notebooks))
            
            # Pipelines are .json files (optional discovery)
            pipelines_dir = customer_dir / "pipelines" 
            pipelines = []
            if pipelines_dir.exists():
                pipelines = self._discover_artifacts_by_pattern(pipelines_dir, "*.json")
            
            artifacts = ArtifactCollection(
                customer_name=customer_name,
                environment=environment,
                lakehouses=[],        # Lakehouses created by Terraform, not files
                pipelines=pipelines,  # .json files
                notebooks=all_notebooks  # .ipynb files
            )
            
            return artifacts
            
        except Exception as e:
            log_config_error(
                self.logger, "DISCOVER_ARTIFACTS", e,
                f"customer={customer_name}, environment={environment}"
            )
            raise ArtifactException(f"Failed to discover artifacts: {str(e)}")
    
    def validate_artifacts_exist(self, customer_name: str, environment: str) -> ArtifactValidation:
        """
        Validate that required artifacts exist for deployment.
        
        Args:
            customer_name: Name of the customer
            environment: Target environment
            
        Returns:
            ArtifactValidation with validation results
            
        Example:
            >>> manager = ArtifactManager(Path("predefined-artifacts"), config_loader)
            >>> validation = manager.validate_artifacts_exist("contoso", "dev")
            >>> if not validation.all_present:
            ...     print(f"Missing: {validation.missing_artifacts}")
        """
        try:
            # Get customer configuration to determine required artifacts
            customer_config = self.config_loader.load_merged_config(customer_name, environment)
            
            # Determine which artifacts should exist based on configuration
            required_artifacts = self._get_required_artifacts(customer_config)
            
            # Check which artifacts actually exist
            artifacts = self.discover_customer_artifacts(customer_name, environment)
            found_artifacts = artifacts.all_artifacts
            
            # Determine missing artifacts
            missing_artifacts = []
            for required in required_artifacts:
                if not any(required in str(artifact) for artifact in found_artifacts):
                    missing_artifacts.append(required)
            
            validation = ArtifactValidation(
                missing_artifacts=missing_artifacts,
                found_artifacts=found_artifacts
            )
            
            log_config_operation(
                self.logger, "VALIDATE_ARTIFACTS",
                f"customer={customer_name}, environment={environment}, "
                f"missing={len(missing_artifacts)}, found={len(found_artifacts)}"
            )
            
            return validation
            
        except Exception as e:
            log_config_error(
                self.logger, "VALIDATE_ARTIFACTS", e,
                f"customer={customer_name}, environment={environment}"
            )
            raise ArtifactException(f"Failed to validate artifacts: {str(e)}")
    
    def get_deployment_order(self, customer_name: str) -> DeploymentOrder:
        """
        Get deployment order configuration for a customer.
        
        Args:
            customer_name: Name of the customer
            
        Returns:
            DeploymentOrder configuration
            
        Raises:
            ArtifactException: If deployment order config is missing or invalid
            
        Example:
            >>> manager = ArtifactManager(Path("notebooks"), config_loader)
            >>> order = manager.get_deployment_order("contoso")
            >>> print(order.phases)  # ['lakehouses', 'pipelines', 'notebooks']
        """
        try:
            # Load deploy-order.yaml from customer configuration
            deploy_order_path = (
                self.config_loader.configs_dir / "customers" / customer_name / "deploy-order.yaml"
            )
            
            validate_file_exists(deploy_order_path, f"Deploy order config for '{customer_name}'")
            deploy_order_config = safe_load_yaml(deploy_order_path)
            
            order = DeploymentOrder(
                phases=deploy_order_config.get("deployment_order", []),
                templates=deploy_order_config.get("templates", {})
            )
            
            log_config_operation(
                self.logger, "LOAD_DEPLOY_ORDER",
                f"customer={customer_name}, phases={len(order.phases)}"
            )
            
            return order
            
        except Exception as e:
            log_config_error(
                self.logger, "LOAD_DEPLOY_ORDER", e,
                f"customer={customer_name}"
            )
            raise ArtifactException(f"Failed to load deployment order: {str(e)}")
    
    def prepare_artifacts_for_terraform(self, artifacts: ArtifactCollection) -> TerraformArtifacts:
        """
        Prepare artifacts for Terraform deployment.
        
        Args:
            artifacts: Collection of artifacts to prepare
            
        Returns:
            TerraformArtifacts ready for deployment
            
        Example:
            >>> artifacts = manager.discover_customer_artifacts("contoso", "dev")
            >>> tf_artifacts = manager.prepare_artifacts_for_terraform(artifacts)
            >>> print(tf_artifacts.variables.keys())
        """
        try:
            # Load customer configuration
            customer_config = self.config_loader.load_merged_config(
                artifacts.customer_name, artifacts.environment
            )
            
            # Prepare Terraform variables from configuration
            tf_variables = self._generate_terraform_variables(customer_config, artifacts)
            
            # Prepare artifact file mappings
            file_mappings = self._create_file_mappings(artifacts)
            
            # Create module configuration
            module_config = self._create_module_config(customer_config, artifacts)
            
            tf_artifacts = TerraformArtifacts(
                variables=tf_variables,
                files=file_mappings,
                module_config=module_config
            )
            
            log_config_operation(
                self.logger, "PREPARE_TF_ARTIFACTS",
                f"customer={artifacts.customer_name}, environment={artifacts.environment}, "
                f"variables={len(tf_variables)}, files={len(file_mappings)}"
            )
            
            return tf_artifacts
            
        except Exception as e:
            log_config_error(
                self.logger, "PREPARE_TF_ARTIFACTS", e,
                f"customer={artifacts.customer_name}, environment={artifacts.environment}"
            )
            raise ArtifactException(f"Failed to prepare Terraform artifacts: {str(e)}")
    
    def validate_artifact_content(self, artifacts: ArtifactCollection) -> ContentValidation:
        """
        Validate the content of discovered artifacts.
        
        Args:
            artifacts: Collection of artifacts to validate
            
        Returns:
            ContentValidation with validation results
            
        Example:
            >>> artifacts = manager.discover_customer_artifacts("contoso", "dev")
            >>> validation = manager.validate_artifact_content(artifacts)
            >>> if not validation.is_valid:
            ...     print(f"Invalid notebooks: {validation.invalid_notebooks}")
        """
        try:
            valid_notebooks = []
            invalid_notebooks = []
            validation_errors = {}
            
            # Validate all notebook files
            for notebook_path in artifacts.all_artifacts:
                try:
                    self._validate_notebook_format(notebook_path)
                    valid_notebooks.append(notebook_path)
                except Exception as e:
                    invalid_notebooks.append(notebook_path)
                    validation_errors[str(notebook_path)] = [str(e)]
            
            validation = ContentValidation(
                valid_notebooks=valid_notebooks,
                invalid_notebooks=invalid_notebooks,
                validation_errors=validation_errors
            )
            
            log_config_operation(
                self.logger, "VALIDATE_CONTENT",
                f"customer={artifacts.customer_name}, environment={artifacts.environment}, "
                f"valid={len(valid_notebooks)}, invalid={len(invalid_notebooks)}"
            )
            
            return validation
            
        except Exception as e:
            log_config_error(
                self.logger, "VALIDATE_CONTENT", e,
                f"customer={artifacts.customer_name}, environment={artifacts.environment}"
            )
            raise ArtifactException(f"Failed to validate artifact content: {str(e)}")
    
    def organize_by_deployment_phase(self, artifacts: ArtifactCollection) -> Dict[str, List[Path]]:
        """
        Organize artifacts by deployment phase.
        
        Args:
            artifacts: Collection of artifacts to organize
            
        Returns:
            Dictionary mapping phase names to artifact lists
            
        Example:
            >>> artifacts = manager.discover_customer_artifacts("contoso", "dev")
            >>> phases = manager.organize_by_deployment_phase(artifacts)
            >>> print(phases.keys())  # ['lakehouses', 'pipelines', 'notebooks']
        """
        try:
            deployment_order = self.get_deployment_order(artifacts.customer_name)
            
            phase_artifacts = {}
            for phase in deployment_order.phases:
                if phase == "lakehouses":
                    phase_artifacts[phase] = artifacts.lakehouses
                elif phase == "pipelines":
                    phase_artifacts[phase] = artifacts.pipelines
                elif phase == "notebooks":
                    phase_artifacts[phase] = artifacts.notebooks
                else:
                    # For unknown phases, include all artifacts
                    phase_artifacts[phase] = artifacts.all_artifacts
            
            log_config_operation(
                self.logger, "ORGANIZE_PHASES",
                f"customer={artifacts.customer_name}, phases={list(phase_artifacts.keys())}"
            )
            
            return phase_artifacts
            
        except Exception as e:
            log_config_error(
                self.logger, "ORGANIZE_PHASES", e,
                f"customer={artifacts.customer_name}"
            )
            raise ArtifactException(f"Failed to organize artifacts by phase: {str(e)}")
    
    def _discover_artifacts_by_pattern(self, directory: Path, pattern: str) -> List[Path]:
        """Discover artifacts in directory matching pattern."""
        try:
            return list(directory.glob(pattern))
        except Exception:
            return []
    
    def _get_required_artifacts(self, customer_config: Dict) -> List[str]:
        """Determine required artifacts based on customer configuration."""
        required = []
        
        # Check architecture configuration for enabled layers
        architecture = customer_config.get("architecture", {}).get("medallion", {})
        
        if architecture.get("bronze_layer", False):
            required.extend(["bronze-processing", "bronze-lakehouse", "bronze-pipeline"])
        
        if architecture.get("silver_layer", False):
            required.extend(["silver-processing", "silver-lakehouse", "silver-pipeline"])
        
        if architecture.get("gold_layer", False):
            required.extend(["gold-processing", "gold-lakehouse", "gold-pipeline"])
        
        return required
    
    def _validate_notebook_format(self, notebook_path: Path) -> None:
        """Validate that notebook file has correct format."""
        try:
            with open(notebook_path, 'r', encoding='utf-8') as f:
                notebook_content = json.load(f)
            
            # Check required notebook fields
            required_fields = ["cells", "metadata", "nbformat"]
            for field in required_fields:
                if field not in notebook_content:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate cells structure
            if not isinstance(notebook_content["cells"], list):
                raise ValueError("Cells must be a list")
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
        except Exception as e:
            raise ValueError(f"Notebook validation failed: {str(e)}")
    
    def _generate_terraform_variables(self, customer_config: Dict, artifacts: ArtifactCollection) -> Dict:
        """Generate Terraform variables from customer configuration and artifacts."""
        # Get template variables from existing ConfigLoader
        template_vars = self.config_loader.prepare_template_variables(
            customer_config, artifacts.environment
        )
        
        # Convert to Terraform-specific variables
        tf_vars = {
            "customer_name": template_vars["customer"]["name"],
            "customer_prefix": template_vars["customer"]["prefix"],
            "environment": template_vars["environment"]["name"],
            "workspace_id": template_vars["environment"]["workspace_id"],
            "fabric_capacity_id": template_vars["capacity"]["fabric_capacity_id"],
            "compute_scale": template_vars["capacity"]["compute_scale"],
            "auto_scale": template_vars["capacity"]["auto_scale"],
            "debug_mode": template_vars["environment"]["debug_mode"],
            "tags": template_vars["tags"],
            "artifact_count": artifacts.total_count,
            "deployment_timestamp": template_vars["deployment"]["timestamp"]
        }
        
        return tf_vars
    
    def _create_file_mappings(self, artifacts: ArtifactCollection) -> Dict[str, Path]:
        """Create file mappings for Terraform."""
        mappings = {}
        
        # Map notebook files by type
        for i, notebook in enumerate(artifacts.notebooks):
            key = f"notebook_{i}_{notebook.stem}"
            mappings[key] = notebook
        
        for i, lakehouse in enumerate(artifacts.lakehouses):
            key = f"lakehouse_{i}_{lakehouse.stem}"
            mappings[key] = lakehouse
        
        for i, pipeline in enumerate(artifacts.pipelines):
            key = f"pipeline_{i}_{pipeline.stem}"
            mappings[key] = pipeline
        
        return mappings
    
    def _create_module_config(self, customer_config: Dict, artifacts: ArtifactCollection) -> Dict:
        """Create module configuration for Terraform."""
        return {
            "customer_solution": {
                "source": "./modules/customer-solution",
                "customer_name": customer_config["customer"]["name"],
                "customer_prefix": customer_config["customer"]["prefix"],
                "environment": artifacts.environment,
                "artifacts": {
                    "notebooks": len(artifacts.notebooks),
                    "lakehouses": len(artifacts.lakehouses), 
                    "pipelines": len(artifacts.pipelines)
                }
            },
            "fabric_workspace": {
                "source": "./modules/fabric-workspace",
                "workspace_id": customer_config["environment"]["workspace_id"],
                "capacity_id": customer_config["capacity"]["fabric_capacity_id"]
            },
            "medallion_architecture": {
                "source": "./modules/medallion-architecture",
                "bronze_enabled": customer_config["architecture"]["medallion"]["bronze_layer"],
                "silver_enabled": customer_config["architecture"]["medallion"]["silver_layer"],
                "gold_enabled": customer_config["architecture"]["medallion"]["gold_layer"]
            }
        }