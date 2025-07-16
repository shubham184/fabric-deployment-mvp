"""
Configuration validation for Microsoft Fabric deployment platform.

This module provides validation functionality for different types of
configuration files using JSON schemas.
"""

from pathlib import Path
from typing import Any, Dict

import jsonschema

from .schema import SchemaManager
from ..utils.logger import get_logger, log_config_error


class ConfigValidator:
    """
    Validates configuration files against JSON schemas.
    
    This class provides methods to validate customer configurations,
    environment configurations, and merged configurations against
    their respective JSON schemas.
    """
    
    def __init__(self, schemas_dir: Path):
        """
        Initialize validator with schema manager.
        
        Args:
            schemas_dir: Path to directory containing JSON schema files
            
        Raises:
            FileNotFoundError: If schemas directory doesn't exist
        """
        self.schema_manager = SchemaManager(schemas_dir)
        self.logger = get_logger(__name__)
        
    def validate_customer_config(self, config: Dict[str, Any]) -> None:
        """
        Validate customer base configuration.
        
        Args:
            config: Customer configuration dictionary to validate
            
        Raises:
            jsonschema.ValidationError: If validation fails with detailed message
            
        Example:
            >>> validator = ConfigValidator(Path("schemas"))
            >>> customer_config = {"customer": {"name": "Test", "prefix": "test"}, ...}
            >>> validator.validate_customer_config(customer_config)
        """
        try:
            self.schema_manager.validate_customer_config(config)
            self.logger.debug("Customer configuration validation passed")
            
        except jsonschema.ValidationError as e:
            log_config_error(self.logger, "VALIDATE_CUSTOMER", e)
            raise jsonschema.ValidationError(
                f"Customer config validation failed: {str(e)}"
            )
    
    def validate_environment_config(self, config: Dict[str, Any]) -> None:
        """
        Validate environment override configuration.
        
        Args:
            config: Environment configuration dictionary to validate
            
        Raises:
            jsonschema.ValidationError: If validation fails with detailed message
            
        Example:
            >>> validator = ConfigValidator(Path("schemas"))
            >>> env_config = {"workspace_id": "123", "capacity_settings": {...}}
            >>> validator.validate_environment_config(env_config)
        """
        try:
            self.schema_manager.validate_environment_config(config)
            self.logger.debug("Environment configuration validation passed")
            
        except jsonschema.ValidationError as e:
            log_config_error(self.logger, "VALIDATE_ENVIRONMENT", e)
            raise jsonschema.ValidationError(
                f"Environment config validation failed: {str(e)}"
            )
    
    def validate_deploy_order_config(self, config: Dict[str, Any]) -> None:
        """
        Validate deployment order configuration.
        
        Args:
            config: Deployment order configuration dictionary to validate
            
        Raises:
            jsonschema.ValidationError: If validation fails with detailed message
            
        Example:
            >>> validator = ConfigValidator(Path("schemas"))
            >>> deploy_config = {"deployment_order": [...], "templates": {...}}
            >>> validator.validate_deploy_order_config(deploy_config)
        """
        try:
            self.schema_manager.validate_deploy_order_config(config)
            self.logger.debug("Deploy order configuration validation passed")
            
        except jsonschema.ValidationError as e:
            log_config_error(self.logger, "VALIDATE_DEPLOY_ORDER", e)
            raise jsonschema.ValidationError(
                f"Deploy order config validation failed: {str(e)}"
            )
    
    def validate_merged_config(self, config: Dict[str, Any]) -> None:
        """
        Validate final merged configuration for completeness.
        
        This performs comprehensive validation to ensure the merged
        configuration has all required fields for template rendering.
        
        Args:
            config: Merged configuration dictionary to validate
            
        Raises:
            ValueError: If required fields are missing or invalid
            
        Example:
            >>> validator = ConfigValidator(Path("schemas"))
            >>> merged_config = {...}  # Complete merged config
            >>> validator.validate_merged_config(merged_config)
        """
        try:
            # Check for required top-level sections
            required_sections = ["customer", "architecture", "capacity"]
            missing_sections = [section for section in required_sections 
                              if section not in config]
            
            if missing_sections:
                raise ValueError(f"Missing required configuration sections: {missing_sections}")
            
            # Validate customer section
            if not config["customer"].get("name"):
                raise ValueError("Customer name is required")
                
            if not config["customer"].get("prefix"):
                raise ValueError("Customer prefix is required")
            
            # Validate architecture section
            medallion_config = config["architecture"].get("medallion", {})
            if not isinstance(medallion_config, dict):
                raise ValueError("Architecture medallion configuration must be a dictionary")
            
            # Validate capacity section
            if not config["capacity"].get("fabric_capacity_id"):
                raise ValueError("Fabric capacity ID is required")
            
            # Check for workspace_id in environment context
            if "workspace_id" in config and not config["workspace_id"]:
                raise ValueError("Workspace ID cannot be empty")
                
            self.logger.debug("Merged configuration validation passed")
            
        except (KeyError, TypeError, ValueError) as e:
            log_config_error(self.logger, "VALIDATE_MERGED", e)
            raise ValueError(f"Merged config validation failed: {str(e)}")
    
    def validate_template_variables(self, variables: Dict[str, Any]) -> None:
        """
        Validate template variables structure for Jinja2 rendering.
        
        Args:
            variables: Template variables dictionary to validate
            
        Raises:
            ValueError: If template variables structure is invalid
            
        Example:
            >>> validator = ConfigValidator(Path("schemas"))
            >>> template_vars = {"customer": {...}, "environment": {...}}
            >>> validator.validate_template_variables(template_vars)
        """
        try:
            # Check for required variable sections
            required_vars = ["customer", "environment", "architecture", "capacity", "tags"]
            missing_vars = [var for var in required_vars if var not in variables]
            
            if missing_vars:
                raise ValueError(f"Missing required template variable sections: {missing_vars}")
            
            # Validate nested structure
            if not isinstance(variables["customer"], dict):
                raise ValueError("Template variables 'customer' must be a dictionary")
                
            if not isinstance(variables["environment"], dict):
                raise ValueError("Template variables 'environment' must be a dictionary")
                
            if not isinstance(variables["tags"], dict):
                raise ValueError("Template variables 'tags' must be a dictionary")
            
            self.logger.debug("Template variables validation passed")
            
        except (KeyError, TypeError, ValueError) as e:
            log_config_error(self.logger, "VALIDATE_TEMPLATE_VARS", e)
            raise ValueError(f"Template variables validation failed: {str(e)}")