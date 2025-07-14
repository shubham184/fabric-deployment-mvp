"""
JSON Schema management for configuration validation.

This module provides functionality to load JSON schemas and validate
configuration data against them for the Microsoft Fabric deployment platform.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

import jsonschema
from jsonschema import Draft7Validator

from ..utils.helpers import validate_file_exists
from ..utils.logger import get_logger


class SchemaManager:
    """
    Manages JSON schemas for configuration validation.
    
    This class handles loading JSON schemas from files and validating
    configuration dictionaries against those schemas.
    """
    
    def __init__(self, schemas_dir: Path):
        """
        Initialize schema manager with schemas directory.
        
        Args:
            schemas_dir: Path to directory containing JSON schema files
            
        Raises:
            FileNotFoundError: If schemas directory doesn't exist
        """
        self.schemas_dir = Path(schemas_dir)
        self.logger = get_logger(__name__)
        
        if not self.schemas_dir.exists():
            raise FileNotFoundError(f"Schemas directory not found: {self.schemas_dir}")
            
        if not self.schemas_dir.is_dir():
            raise FileNotFoundError(f"Schemas path is not a directory: {self.schemas_dir}")
            
        self._schema_cache: Dict[str, Dict[str, Any]] = {}
        
    def load_schema(self, schema_name: str) -> Dict[str, Any]:
        """
        Load a JSON schema from file with caching.
        
        Args:
            schema_name: Name of schema file (without .json extension)
            
        Returns:
            Loaded JSON schema as dictionary
            
        Raises:
            FileNotFoundError: If schema file doesn't exist
            json.JSONDecodeError: If schema file contains invalid JSON
            
        Example:
            >>> manager = SchemaManager(Path("schemas"))
            >>> schema = manager.load_schema("customer-config")
        """
        if schema_name in self._schema_cache:
            return self._schema_cache[schema_name]
            
        schema_path = self.schemas_dir / f"{schema_name}.schema.json"
        validate_file_exists(schema_path, f"Schema file '{schema_name}'")
        
        try:
            with open(schema_path, 'r', encoding='utf-8') as file:
                schema = json.load(file)
                
            # Validate that it's a valid JSON schema
            Draft7Validator.check_schema(schema)
            
            self._schema_cache[schema_name] = schema
            self.logger.debug(f"Loaded schema: {schema_name}")
            
            return schema
            
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Invalid JSON in schema file {schema_path}: {str(e)}",
                e.doc, e.pos
            )
        except jsonschema.SchemaError as e:
            raise jsonschema.SchemaError(f"Invalid JSON schema in {schema_path}: {str(e)}")
    
    def validate_against_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> None:
        """
        Validate data against a JSON schema.
        
        Args:
            data: Data to validate
            schema: JSON schema to validate against
            
        Raises:
            jsonschema.ValidationError: If data doesn't match schema
            
        Example:
            >>> manager = SchemaManager(Path("schemas"))
            >>> schema = manager.load_schema("customer-config")
            >>> manager.validate_against_schema(config_data, schema)
        """
        try:
            validator = Draft7Validator(schema)
            validator.validate(data)
            
        except jsonschema.ValidationError as e:
            # Create more user-friendly error message
            path = " -> ".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
            
            error_msg = f"Validation failed at '{path}': {e.message}"
            
            if e.validator == "required":
                missing_props = e.validator_value
                error_msg = f"Missing required properties at '{path}': {missing_props}"
            elif e.validator == "pattern":
                error_msg = f"Value at '{path}' doesn't match required pattern: {e.validator_value}"
            elif e.validator == "enum":
                allowed_values = e.validator_value
                error_msg = f"Value at '{path}' must be one of: {allowed_values}"
                
            raise jsonschema.ValidationError(error_msg)
    
    def get_available_schemas(self) -> List[str]:
        """
        Get list of available schema names in the schemas directory.
        
        Returns:
            List of schema names (without .schema.json extension)
            
        Example:
            >>> manager = SchemaManager(Path("schemas"))
            >>> schemas = manager.get_available_schemas()
            >>> print(schemas)  # ['customer-config', 'environment', 'deploy-order']
        """
        schema_files = self.schemas_dir.glob("*.schema.json")
        return [f.stem.replace(".schema", "") for f in schema_files]
    
    def validate_customer_config(self, config: Dict[str, Any]) -> None:
        """
        Validate customer configuration against customer-config schema.
        
        Args:
            config: Customer configuration to validate
            
        Raises:
            jsonschema.ValidationError: If validation fails
        """
        schema = self.load_schema("customer-config")
        self.validate_against_schema(config, schema)
        self.logger.debug("Customer config validation passed")
    
    def validate_environment_config(self, config: Dict[str, Any]) -> None:
        """
        Validate environment configuration against environment schema.
        
        Args:
            config: Environment configuration to validate
            
        Raises:
            jsonschema.ValidationError: If validation fails
        """
        schema = self.load_schema("environment")
        self.validate_against_schema(config, schema)
        self.logger.debug("Environment config validation passed")
    
    def validate_deploy_order_config(self, config: Dict[str, Any]) -> None:
        """
        Validate deployment order configuration against deploy-order schema.
        
        Args:
            config: Deployment order configuration to validate
            
        Raises:
            jsonschema.ValidationError: If validation fails
        """
        schema = self.load_schema("deploy-order")
        self.validate_against_schema(config, schema)
        self.logger.debug("Deploy order config validation passed")