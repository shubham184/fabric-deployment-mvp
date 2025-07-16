"""
Comprehensive unit tests for the configuration loader system.

This module tests all aspects of the configuration loading, merging,
validation, and template variable preparation functionality.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import jsonschema
import yaml

from src.config.loader import ConfigLoader
from src.config.validator import ConfigValidator
from src.config.schema import SchemaManager
from src.utils.helpers import deep_merge


class TestConfigLoader(unittest.TestCase):
    """Test cases for ConfigLoader class."""
    
    def setUp(self):
        """Set up test fixtures with temporary directory structure."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        
        # Create directory structure
        self.configs_dir = self.temp_path / "configs"
        self.schemas_dir = self.configs_dir / "schemas"
        self.defaults_dir = self.configs_dir / "defaults"
        self.customers_dir = self.configs_dir / "customers"
        
        for directory in [self.configs_dir, self.schemas_dir, self.defaults_dir, self.customers_dir]:
            directory.mkdir(parents=True)
        
        # Create test schemas
        self._create_test_schemas()
        
        # Create test configurations
        self._create_test_configs()
        
        # Initialize loader
        self.loader = ConfigLoader(self.configs_dir, self.schemas_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    def _create_test_schemas(self):
        """Create minimal JSON schemas for testing."""
        customer_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["customer", "architecture", "capacity"],
            "properties": {
                "customer": {
                    "type": "object",
                    "required": ["name", "prefix"],
                    "properties": {
                        "name": {"type": "string"},
                        "prefix": {"type": "string", "pattern": "^[a-z]{2,6}$"}
                    }
                },
                "architecture": {
                    "type": "object",
                    "required": ["medallion"],
                    "properties": {
                        "medallion": {
                            "type": "object",
                            "required": ["bronze_layer", "silver_layer", "gold_layer"],
                            "properties": {
                                "bronze_layer": {"type": "boolean"},
                                "silver_layer": {"type": "boolean"},
                                "gold_layer": {"type": "boolean"}
                            }
                        }
                    }
                },
                "capacity": {
                    "type": "object",
                    "required": ["fabric_capacity_id"],
                    "properties": {
                        "fabric_capacity_id": {"type": "string"}
                    }
                }
            }
        }
        
        environment_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["workspace_id", "capacity_settings"],
            "properties": {
                "workspace_id": {"type": "string"},
                "capacity_settings": {
                    "type": "object",
                    "required": ["compute_scale", "auto_scale"],
                    "properties": {
                        "compute_scale": {"type": "string", "enum": ["small", "medium", "large"]},
                        "auto_scale": {"type": "boolean"}
                    }
                }
            }
        }
        
        # Write schemas to files
        with open(self.schemas_dir / "customer-config.schema.json", 'w') as f:
            json.dump(customer_schema, f)
            
        with open(self.schemas_dir / "environment.schema.json", 'w') as f:
            json.dump(environment_schema, f)
    
    def _create_test_configs(self):
        """Create test configuration files."""
        # Default architecture
        default_architecture = {
            "architecture": {
                "medallion": {
                    "bronze_layer": True,
                    "silver_layer": True,
                    "gold_layer": True
                }
            }
        }
        
        # Default environments
        default_environments = {
            "dev": {
                "capacity_settings": {
                    "compute_scale": "small",
                    "auto_scale": False
                },
                "debug_mode": True
            },
            "prod": {
                "capacity_settings": {
                    "compute_scale": "large",
                    "auto_scale": True
                },
                "debug_mode": False
            }
        }
        
        # Sample customer base config
        customer_base = {
            "customer": {
                "name": "Test Corp",
                "prefix": "test"
            },
            "architecture": {
                "medallion": {
                    "bronze_layer": True,
                    "silver_layer": True,
                    "gold_layer": True
                }
            },
            "capacity": {
                "fabric_capacity_id": "F64-test-001"
            },
            "advanced": {
                "custom_tags": {
                    "customer": "test-corp",
                    "project": "data-platform"
                }
            }
        }
        
        # Environment configs
        dev_env = {
            "workspace_id": "dev-workspace-123",
            "capacity_settings": {
                "compute_scale": "small",
                "auto_scale": False
            },
            "environment_tags": {
                "environment": "development"
            },
            "debug_mode": True
        }
        
        prod_env = {
            "workspace_id": "prod-workspace-456",
            "capacity_settings": {
                "compute_scale": "large",
                "auto_scale": True
            },
            "environment_tags": {
                "environment": "production"
            },
            "debug_mode": False
        }
        
        # Write configuration files
        with open(self.defaults_dir / "architecture.yaml", 'w') as f:
            yaml.dump(default_architecture, f)
            
        with open(self.defaults_dir / "environments.yaml", 'w') as f:
            yaml.dump(default_environments, f)
        
        # Create customer directory and configs
        test_customer_dir = self.customers_dir / "test-customer"
        test_customer_env_dir = test_customer_dir / "environments"
        test_customer_dir.mkdir()
        test_customer_env_dir.mkdir()
        
        with open(test_customer_dir / "base.yaml", 'w') as f:
            yaml.dump(customer_base, f)
            
        with open(test_customer_env_dir / "dev.yaml", 'w') as f:
            yaml.dump(dev_env, f)
            
        with open(test_customer_env_dir / "prod.yaml", 'w') as f:
            yaml.dump(prod_env, f)
    
    def test_loader_initialization(self):
        """Test ConfigLoader initialization."""
        # Test successful initialization
        loader = ConfigLoader(self.configs_dir, self.schemas_dir)
        self.assertIsInstance(loader, ConfigLoader)
        
        # Test with non-existent configs directory
        with self.assertRaises(FileNotFoundError):
            ConfigLoader(Path("/non/existent"), self.schemas_dir)
        
        # Test with non-existent schemas directory
        with self.assertRaises(FileNotFoundError):
            ConfigLoader(self.configs_dir, Path("/non/existent"))
    
    def test_load_defaults(self):
        """Test loading default configurations."""
        defaults = self.loader.load_defaults()
        
        # Verify structure
        self.assertIn("architecture", defaults)
        self.assertIn("environments", defaults)
        
        # Verify architecture defaults
        arch = defaults["architecture"]["medallion"]
        self.assertTrue(arch["bronze_layer"])
        self.assertTrue(arch["silver_layer"])
        self.assertTrue(arch["gold_layer"])
        
        # Verify environment defaults
        self.assertIn("dev", defaults["environments"])
        self.assertIn("prod", defaults["environments"])
        
        # Test caching
        defaults2 = self.loader.load_defaults()
        self.assertIs(defaults, defaults2)  # Should return cached instance
    
    def test_load_customer_base(self):
        """Test loading customer base configuration."""
        config = self.loader.load_customer_base("test-customer")
        
        # Verify customer information
        self.assertEqual(config["customer"]["name"], "Test Corp")
        self.assertEqual(config["customer"]["prefix"], "test")
        
        # Verify capacity information
        self.assertEqual(config["capacity"]["fabric_capacity_id"], "F64-test-001")
        
        # Test with non-existent customer
        with self.assertRaises(FileNotFoundError):
            self.loader.load_customer_base("non-existent-customer")
    
    def test_load_environment_override(self):
        """Test loading environment override configuration."""
        dev_config = self.loader.load_environment_override("test-customer", "dev")
        
        # Verify workspace ID
        self.assertEqual(dev_config["workspace_id"], "dev-workspace-123")
        
        # Verify capacity settings
        self.assertEqual(dev_config["capacity_settings"]["compute_scale"], "small")
        self.assertFalse(dev_config["capacity_settings"]["auto_scale"])
        
        # Verify debug mode
        self.assertTrue(dev_config["debug_mode"])
        
        # Test with non-existent environment
        with self.assertRaises(FileNotFoundError):
            self.loader.load_environment_override("test-customer", "non-existent")
    
    def test_load_merged_config(self):
        """Test configuration merging with inheritance."""
        merged = self.loader.load_merged_config("test-customer", "dev")
        
        # Verify customer information is preserved
        self.assertEqual(merged["customer"]["name"], "Test Corp")
        self.assertEqual(merged["customer"]["prefix"], "test")
        
        # Verify capacity information is merged
        self.assertEqual(merged["capacity"]["fabric_capacity_id"], "F64-test-001")
        
        # Verify environment information is added
        self.assertEqual(merged["environment"]["name"], "dev")
        self.assertEqual(merged["environment"]["workspace_id"], "dev-workspace-123")
        
        # Verify capacity settings are merged
        self.assertEqual(merged["capacity_settings"]["compute_scale"], "small")
        self.assertFalse(merged["capacity_settings"]["auto_scale"])
        
        # Verify debug mode is set
        self.assertTrue(merged["debug_mode"])
    
    def test_prepare_template_variables(self):
        """Test template variable preparation."""
        merged_config = self.loader.load_merged_config("test-customer", "dev")
        variables = self.loader.prepare_template_variables(merged_config, "dev")
        
        # Verify nested structure
        required_sections = ["customer", "environment", "architecture", "capacity", "tags", "deployment"]
        for section in required_sections:
            self.assertIn(section, variables)
        
        # Verify customer section
        self.assertEqual(variables["customer"]["name"], "Test Corp")
        self.assertEqual(variables["customer"]["prefix"], "test")
        
        # Verify environment section
        self.assertEqual(variables["environment"]["name"], "dev")
        self.assertEqual(variables["environment"]["workspace_id"], "dev-workspace-123")
        self.assertTrue(variables["environment"]["debug_mode"])
        
        # Verify architecture section
        self.assertTrue(variables["architecture"]["bronze_layer"])
        self.assertTrue(variables["architecture"]["silver_layer"])
        self.assertTrue(variables["architecture"]["gold_layer"])
        
        # Verify capacity section
        self.assertEqual(variables["capacity"]["fabric_capacity_id"], "F64-test-001")
        self.assertEqual(variables["capacity"]["compute_scale"], "small")
        
        # Verify tags are merged
        self.assertIn("customer", variables["tags"])
        self.assertIn("environment", variables["tags"])
        
        # Verify deployment metadata
        self.assertIn("timestamp", variables["deployment"])
        self.assertEqual(variables["deployment"]["version"], "1.0.0")
        self.assertEqual(variables["deployment"]["customer"], "Test Corp")
        self.assertEqual(variables["deployment"]["environment"], "dev")
    
    def test_deep_merge_functionality(self):
        """Test deep merge configuration functionality."""
        config1 = {
            "a": {"x": 1, "y": 2},
            "b": 3
        }
        config2 = {
            "a": {"y": 20, "z": 30},
            "c": 4
        }
        
        merged = self.loader._deep_merge_configs(config1, config2)
        
        expected = {
            "a": {"x": 1, "y": 20, "z": 30},
            "b": 3,
            "c": 4
        }
        
        self.assertEqual(merged, expected)
    
    def test_get_customer_list(self):
        """Test getting list of available customers."""
        customers = self.loader.get_customer_list()
        self.assertIn("test-customer", customers)
    
    def test_get_customer_environments(self):
        """Test getting list of customer environments."""
        environments = self.loader.get_customer_environments("test-customer")
        self.assertIn("dev", environments)
        self.assertIn("prod", environments)
    
    def test_validation_errors(self):
        """Test configuration validation error handling."""
        # Create invalid customer config
        invalid_customer_dir = self.customers_dir / "invalid-customer"
        invalid_customer_dir.mkdir()
        
        invalid_config = {
            "customer": {
                "name": "Invalid Corp",
                "prefix": "INVALID123"  # Invalid prefix format
            }
        }
        
        with open(invalid_customer_dir / "base.yaml", 'w') as f:
            yaml.dump(invalid_config, f)
        
        # Should raise validation error
        with self.assertRaises(jsonschema.ValidationError):
            self.loader.load_customer_base("invalid-customer")
    
    def test_missing_file_errors(self):
        """Test error handling for missing files."""
        # Test missing customer
        with self.assertRaises(FileNotFoundError) as cm:
            self.loader.load_customer_base("missing-customer")
        
        self.assertIn("Customer base config", str(cm.exception))
        self.assertIn("missing-customer", str(cm.exception))
        
        # Test missing environment
        with self.assertRaises(FileNotFoundError) as cm:
            self.loader.load_environment_override("test-customer", "missing-env")
        
        self.assertIn("Environment config", str(cm.exception))
        self.assertIn("missing-env", str(cm.exception))


class TestHelperFunctions(unittest.TestCase):
    """Test cases for helper functions."""
    
    def test_deep_merge(self):
        """Test deep merge functionality."""
        from src.utils.helpers import deep_merge
        
        dict1 = {
            "level1": {
                "level2": {
                    "key1": "value1",
                    "key2": "value2"
                },
                "other": "data"
            },
            "top": "level"
        }
        
        dict2 = {
            "level1": {
                "level2": {
                    "key2": "new_value2",
                    "key3": "value3"
                },
                "new_other": "new_data"
            },
            "new_top": "new_level"
        }
        
        result = deep_merge(dict1, dict2)
        
        expected = {
            "level1": {
                "level2": {
                    "key1": "value1",
                    "key2": "new_value2",
                    "key3": "value3"
                },
                "other": "data",
                "new_other": "new_data"
            },
            "top": "level",
            "new_top": "new_level"
        }
        
        self.assertEqual(result, expected)
    
    def test_merge_tags(self):
        """Test tag merging functionality."""
        from src.utils.helpers import merge_tags
        
        tags1 = {"customer": "test", "project": "analytics"}
        tags2 = {"environment": "dev", "customer": "test-dev"}
        tags3 = {"team": "data"}
        
        result = merge_tags(tags1, tags2, tags3)
        
        expected = {
            "customer": "test-dev",  # Last one wins
            "project": "analytics",
            "environment": "dev",
            "team": "data"
        }
        
        self.assertEqual(result, expected)


class TestSchemaManager(unittest.TestCase):
    """Test cases for SchemaManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.schemas_dir = Path(self.temp_dir.name)
        
        # Create test schema
        test_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"}
            }
        }
        
        with open(self.schemas_dir / "test.schema.json", 'w') as f:
            json.dump(test_schema, f)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    def test_schema_loading(self):
        """Test schema loading and caching."""
        manager = SchemaManager(self.schemas_dir)
        
        # Load schema
        schema = manager.load_schema("test")
        self.assertIn("properties", schema)
        self.assertIn("name", schema["properties"])
        
        # Test caching
        schema2 = manager.load_schema("test")
        self.assertIs(schema, schema2)
    
    def test_schema_validation(self):
        """Test data validation against schema."""
        manager = SchemaManager(self.schemas_dir)
        schema = manager.load_schema("test")
        
        # Valid data
        valid_data = {"name": "test"}
        manager.validate_against_schema(valid_data, schema)  # Should not raise
        
        # Invalid data
        invalid_data = {"other": "value"}
        with self.assertRaises(jsonschema.ValidationError):
            manager.validate_against_schema(invalid_data, schema)


if __name__ == "__main__":
    unittest.main()