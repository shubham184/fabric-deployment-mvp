"""
Enhanced configuration loader for Microsoft Fabric deployment platform.

This module provides the main ConfigLoader class that handles configuration
inheritance, validation, and template variable preparation for the deployment
platform.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import jsonschema

from .validator import ConfigValidator
from ..utils.helpers import deep_merge, safe_load_yaml, validate_file_exists, merge_tags
from ..utils.logger import get_logger, log_config_operation, log_config_error


class ConfigLoader:
    """
    Enhanced configuration loader with inheritance and validation.
    
    This class handles loading and merging configurations from multiple sources:
    1. Default configurations (configs/defaults/)
    2. Customer base configurations (configs/customers/{customer}/base.yaml)
    3. Environment overrides (configs/customers/{customer}/environments/{env}.yaml)
    
    It also prepares nested template variables for Jinja2 rendering.
    """
    
    def __init__(self, configs_dir: Path, schemas_dir: Path):
        """
        Initialize configuration loader.
        
        Args:
            configs_dir: Path to configuration files directory
            schemas_dir: Path to JSON schema files directory
            
        Raises:
            FileNotFoundError: If required directories don't exist
            
        Example:
            >>> loader = ConfigLoader(
            ...     configs_dir=Path("configs"),
            ...     schemas_dir=Path("configs/schemas")
            ... )
        """
        self.configs_dir = Path(configs_dir)
        self.schemas_dir = Path(schemas_dir)
        self.logger = get_logger(__name__)
        
        # Validate required directories exist
        if not self.configs_dir.exists():
            raise FileNotFoundError(f"Configs directory not found: {self.configs_dir}")
            
        if not self.schemas_dir.exists():
            raise FileNotFoundError(f"Schemas directory not found: {self.schemas_dir}")
        
        # Initialize validator
        self.validator = ConfigValidator(self.schemas_dir)
        
        # Cache for loaded configurations
        self._defaults_cache: Optional[Dict[str, Any]] = None
        
        log_config_operation(self.logger, "INIT", f"configs_dir={self.configs_dir}, schemas_dir={self.schemas_dir}")
    
    def load_defaults(self) -> Dict[str, Any]:
        """
        Load default configurations from defaults directory.
        
        Returns:
            Dictionary containing default architecture and environment settings
            
        Raises:
            FileNotFoundError: If default files don't exist
            yaml.YAMLError: If default files contain invalid YAML
            
        Example:
            >>> loader = ConfigLoader(Path("configs"), Path("schemas"))
            >>> defaults = loader.load_defaults()
            >>> print(defaults["architecture"]["medallion"])
        """
        if self._defaults_cache is not None:
            return self._defaults_cache
            
        try:
            defaults_dir = self.configs_dir / "defaults"
            
            # Load default architecture
            architecture_path = defaults_dir / "architecture.yaml"
            architecture_defaults = safe_load_yaml(architecture_path)
            
            # Load default environments
            environments_path = defaults_dir / "environments.yaml"
            environment_defaults = safe_load_yaml(environments_path)
            
            defaults = {
                "architecture": architecture_defaults.get("architecture", {}),
                "environments": environment_defaults
            }
            
            self._defaults_cache = defaults
            log_config_operation(self.logger, "LOAD_DEFAULTS", "Successfully loaded default configurations")
            
            return defaults
            
        except Exception as e:
            log_config_error(self.logger, "LOAD_DEFAULTS", e)
            raise
    
    def load_customer_base(self, customer_name: str) -> Dict[str, Any]:
        """
        Load customer base configuration.
        
        Args:
            customer_name: Name of the customer
            
        Returns:
            Customer base configuration dictionary
            
        Raises:
            FileNotFoundError: If customer base config doesn't exist
            yaml.YAMLError: If customer config contains invalid YAML
            jsonschema.ValidationError: If customer config fails validation
            
        Example:
            >>> loader = ConfigLoader(Path("configs"), Path("schemas"))
            >>> config = loader.load_customer_base("sample-customer")
            >>> print(config["customer"]["name"])
        """
        try:
            customer_base_path = self.configs_dir / "customers" / customer_name / "base.yaml"
            validate_file_exists(
                customer_base_path, 
                f"Customer base config for '{customer_name}'"
            )
            
            config = safe_load_yaml(customer_base_path)
            
            # Validate against schema
            self.validator.validate_customer_config(config)
            
            log_config_operation(self.logger, "LOAD_CUSTOMER", f"customer='{customer_name}'")
            return config
            
        except Exception as e:
            log_config_error(self.logger, "LOAD_CUSTOMER", e, f"customer='{customer_name}'")
            raise
    
    def load_environment_override(self, customer_name: str, environment: str) -> Dict[str, Any]:
        """
        Load environment-specific override configuration.
        
        Args:
            customer_name: Name of the customer
            environment: Environment name (dev, test, prod)
            
        Returns:
            Environment override configuration dictionary
            
        Raises:
            FileNotFoundError: If environment config doesn't exist
            yaml.YAMLError: If environment config contains invalid YAML
            jsonschema.ValidationError: If environment config fails validation
            
        Example:
            >>> loader = ConfigLoader(Path("configs"), Path("schemas"))
            >>> override = loader.load_environment_override("sample-customer", "dev")
            >>> print(override["workspace_id"])
        """
        try:
            env_override_path = (
                self.configs_dir / "customers" / customer_name / 
                "environments" / f"{environment}.yaml"
            )
            validate_file_exists(
                env_override_path,
                f"Environment config for '{customer_name}' environment '{environment}'"
            )
            
            config = safe_load_yaml(env_override_path)
            
            # Validate against schema
            self.validator.validate_environment_config(config)
            
            log_config_operation(
                self.logger, "LOAD_ENVIRONMENT", 
                f"customer='{customer_name}', environment='{environment}'"
            )
            return config
            
        except Exception as e:
            log_config_error(
                self.logger, "LOAD_ENVIRONMENT", e,
                f"customer='{customer_name}', environment='{environment}'"
            )
            raise
    
    def load_merged_config(self, customer_name: str, environment: str) -> Dict[str, Any]:
        """
        Load and merge configurations with inheritance: defaults → customer → environment.
        
        Args:
            customer_name: Name of the customer
            environment: Environment name (dev, test, prod)
            
        Returns:
            Fully merged configuration dictionary
            
        Raises:
            FileNotFoundError: If any required config files don't exist
            jsonschema.ValidationError: If any configs fail validation
            
        Example:
            >>> loader = ConfigLoader(Path("configs"), Path("schemas"))
            >>> merged = loader.load_merged_config("sample-customer", "dev")
            >>> print(merged["customer"]["name"])
        """
        try:
            # Load all configuration sources
            defaults = self.load_defaults()
            customer_base = self.load_customer_base(customer_name)
            env_override = self.load_environment_override(customer_name, environment)
            
            # Start with default architecture
            merged_config = deep_merge({}, defaults["architecture"])
            
            # Merge customer base configuration
            merged_config = deep_merge(merged_config, customer_base)
            
            # Apply environment-specific defaults
            env_defaults = defaults["environments"].get(environment, {})
            merged_config = deep_merge(merged_config, env_defaults)
            
            # Apply environment overrides
            merged_config = deep_merge(merged_config, env_override)
            
            # Add environment name for reference
            merged_config["environment"] = {"name": environment}
            if "workspace_id" in env_override:
                merged_config["environment"]["workspace_id"] = env_override["workspace_id"]
            
            # Validate final merged configuration
            self.validator.validate_merged_config(merged_config)
            
            log_config_operation(
                self.logger, "MERGE_CONFIG",
                f"customer='{customer_name}', environment='{environment}'"
            )
            
            return merged_config
            
        except Exception as e:
            log_config_error(
                self.logger, "MERGE_CONFIG", e,
                f"customer='{customer_name}', environment='{environment}'"
            )
            raise
    
    def prepare_template_variables(self, merged_config: Dict[str, Any], environment: str) -> Dict[str, Any]:
        """
        Prepare nested template variables for Jinja2 rendering.
        
        Args:
            merged_config: Merged configuration dictionary
            environment: Environment name
            
        Returns:
            Nested template variables dictionary optimized for Jinja2
            
        Raises:
            ValueError: If required configuration sections are missing
            
        Example:
            >>> loader = ConfigLoader(Path("configs"), Path("schemas"))
            >>> merged = loader.load_merged_config("sample-customer", "dev")
            >>> variables = loader.prepare_template_variables(merged, "dev")
            >>> # Use in Jinja2: template.render(**variables)
        """
        try:
            # Extract customer information
            customer_info = merged_config.get("customer", {})
            
            # Extract environment information
            env_info = merged_config.get("environment", {})
            env_info.update({
                "name": environment,
                "debug_mode": merged_config.get("debug_mode", False)
            })
            
            # Extract architecture settings (flatten medallion for easier access)
            architecture = merged_config.get("architecture", {}).get("medallion", {})
            
            # Extract and merge capacity settings
            capacity_info = merged_config.get("capacity", {}).copy()
            if "capacity_settings" in merged_config:
                capacity_info.update(merged_config["capacity_settings"])
            
            # Merge all tags from different sources
            customer_tags = merged_config.get("advanced", {}).get("custom_tags", {})
            environment_tags = merged_config.get("environment_tags", {})
            all_tags = merge_tags(customer_tags, environment_tags)
            
            # Create deployment metadata
            deployment_info = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0",
                "customer": customer_info.get("name", ""),
                "environment": environment
            }
            
            # Prepare final template variables with nested structure
            template_variables = {
                "customer": customer_info,
                "environment": env_info,
                "architecture": architecture,
                "capacity": capacity_info,
                "tags": all_tags,
                "deployment": deployment_info
            }
            
            # Validate template variables structure
            self.validator.validate_template_variables(template_variables)
            
            log_config_operation(
                self.logger, "PREPARE_VARIABLES",
                f"environment='{environment}', variables_count={len(template_variables)}"
            )
            
            return template_variables
            
        except Exception as e:
            log_config_error(
                self.logger, "PREPARE_VARIABLES", e,
                f"environment='{environment}'"
            )
            raise
    
    def _deep_merge_configs(self, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge multiple configuration dictionaries.
        
        Args:
            *configs: Variable number of configuration dictionaries
            
        Returns:
            Merged configuration dictionary
            
        Example:
            >>> loader = ConfigLoader(Path("configs"), Path("schemas"))
            >>> merged = loader._deep_merge_configs(config1, config2, config3)
        """
        result = {}
        for config in configs:
            if config:
                result = deep_merge(result, config)
        return result
    
    def get_customer_list(self) -> list[str]:
        """
        Get list of available customers.
        
        Returns:
            List of customer directory names
            
        Example:
            >>> loader = ConfigLoader(Path("configs"), Path("schemas"))
            >>> customers = loader.get_customer_list()
            >>> print(customers)  # ['sample-customer', 'customer-template']
        """
        customers_dir = self.configs_dir / "customers"
        if not customers_dir.exists():
            return []
            
        return [
            d.name for d in customers_dir.iterdir() 
            if d.is_dir() and (d / "base.yaml").exists()
        ]
    
    def get_customer_environments(self, customer_name: str) -> list[str]:
        """
        Get list of available environments for a customer.
        
        Args:
            customer_name: Name of the customer
            
        Returns:
            List of environment names
            
        Example:
            >>> loader = ConfigLoader(Path("configs"), Path("schemas"))
            >>> envs = loader.get_customer_environments("sample-customer")
            >>> print(envs)  # ['dev', 'test', 'prod']
        """
        env_dir = self.configs_dir / "customers" / customer_name / "environments"
        if not env_dir.exists():
            return []
            
        return [
            f.stem for f in env_dir.glob("*.yaml")
            if f.is_file()
        ]