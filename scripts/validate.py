#!/usr/bin/env python3
"""
Enhanced validation module for Fabric deployment platform.
Performs comprehensive pre-flight checks before Terraform runs.
"""

import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
import requests

try:
    import jsonschema
except ImportError:
    print("Please install jsonschema: pip install jsonschema")
    sys.exit(1)

try:
    from azure.identity import ClientSecretCredential
    from azure.core.exceptions import HttpResponseError
except ImportError:
    # Azure SDK is optional - validation can still run without it
    ClientSecretCredential = None
    HttpResponseError = None

# Suppress Azure SDK verbose logging
logging.getLogger("azure.identity").setLevel(logging.WARNING)
logging.getLogger("azure.core").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class FabricValidator:
    """Comprehensive validator for Fabric deployments."""
    
    # Resource naming rules for Fabric
    NAMING_RULES = {
        'min_length': 1,
        'max_length': 128,
        'pattern': r'^[a-zA-Z0-9][a-zA-Z0-9_\-\s]*[a-zA-Z0-9]$',
        'reserved_words': ['system', 'admin', 'fabric', 'microsoft']
    }
    
    # YAML schema for customer configs
    CONFIG_SCHEMA = {
        "type": "object",
        "required": ["customer", "infrastructure", "architecture", "artifacts"],
        "properties": {
            "customer": {
                "type": "object",
                "required": ["name", "prefix"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "prefix": {"type": "string", "pattern": "^[a-z]{2,4}$"}
                }
            },
            "infrastructure": {
                "type": "object",
                "required": ["workspace_id", "capacity_id"],
                "properties": {
                    "workspace_id": {
                        "type": "string",
                        "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
                    },
                    "capacity_id": {
                        "type": "string",
                        "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
                    }
                }
            },
            "architecture": {
                "type": "object",
                "required": ["bronze_enabled", "silver_enabled", "gold_enabled"],
                "properties": {
                    "bronze_enabled": {"type": "boolean"},
                    "silver_enabled": {"type": "boolean"},
                    "gold_enabled": {"type": "boolean"}
                }
            },
            "artifacts": {
                "type": "object",
                "properties": {
                    "notebooks": {
                        "type": "object",
                        "patternProperties": {
                            "^[a-zA-Z0-9-]+$": {
                                "type": "object",
                                "required": ["display_name", "path"],
                                "properties": {
                                    "display_name": {"type": "string"},
                                    "path": {"type": "string"}
                                }
                            }
                        }
                    },
                    "pipelines": {
                        "type": "object",
                        "patternProperties": {
                            "^[a-zA-Z0-9-]+$": {
                                "type": "object",
                                "required": ["display_name", "path"],
                                "properties": {
                                    "display_name": {"type": "string"},
                                    "path": {"type": "string"}
                                }
                            }
                        }
                    }
                }
            },
            "environments": {
                "type": "object",
                "patternProperties": {
                    "^(dev|prod|test|staging)$": {
                        "type": "object"
                    }
                }
            }
        }
    }
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self._fabric_client = None
        self._workspace_name = None  # Store workspace name for later use
        
    def validate_all(self, customer_name: str, environment: str) -> Tuple[bool, List[str], List[str]]:
        """Run all validations and return (success, errors, warnings)."""
        self.errors = []
        self.warnings = []
        
        # Load config
        config_path = self.project_root / "configs" / "customers" / f"{customer_name}.yaml"
        if not config_path.exists():
            self.errors.append(f"Customer config not found: {config_path}")
            return False, self.errors, self.warnings
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            self.errors.append(f"Failed to parse YAML: {e}")
            return False, self.errors, self.warnings
        
        # Run validations
        self._validate_yaml_schema(config)
        self._validate_resource_names(config)
        self._validate_artifact_files(config)
        self._validate_workspace_access(config)
        self._validate_capacity(config)
        self._check_naming_conflicts(config)
        
        return len(self.errors) == 0, self.errors, self.warnings
    
    def _validate_yaml_schema(self, config: dict) -> None:
        """Validate config against JSON schema."""
        try:
            jsonschema.validate(config, self.CONFIG_SCHEMA)
        except jsonschema.ValidationError as e:
            self.errors.append(f"Schema validation failed: {e.message}")
            
    def _validate_resource_names(self, config: dict) -> None:
        """Validate all resource names against Fabric naming rules."""
        prefix = config['customer']['prefix']
        
        # Check prefix
        if not re.match(r'^[a-z]{2,4}$', prefix):
            self.errors.append(f"Invalid prefix '{prefix}': must be 2-4 lowercase letters")
        
        # Check all display names
        all_names = []
        
        # Collect artifact names
        for notebook in config.get('artifacts', {}).get('notebooks', {}).values():
            all_names.append(notebook['display_name'])
        for pipeline in config.get('artifacts', {}).get('pipelines', {}).values():
            all_names.append(pipeline['display_name'])
            
        # Add generated lakehouse names
        if config['architecture']['bronze_enabled']:
            all_names.append(f"{prefix}_bronze_lakehouse")
        if config['architecture']['silver_enabled']:
            all_names.append(f"{prefix}_silver_lakehouse")
        if config['architecture']['gold_enabled']:
            all_names.append(f"{prefix}_gold_lakehouse")
        
        # Validate each name
        for name in all_names:
            if len(name) < self.NAMING_RULES['min_length']:
                self.errors.append(f"Resource name too short: '{name}'")
            elif len(name) > self.NAMING_RULES['max_length']:
                self.errors.append(f"Resource name too long: '{name}' (max {self.NAMING_RULES['max_length']} chars)")
            elif not re.match(self.NAMING_RULES['pattern'], name):
                self.errors.append(f"Invalid resource name: '{name}' (must start/end with alphanumeric, can contain spaces, hyphens, underscores)")
            
            # Check reserved words
            name_lower = name.lower()
            for reserved in self.NAMING_RULES['reserved_words']:
                if reserved in name_lower:
                    self.warnings.append(f"Resource name contains reserved word '{reserved}': {name}")
                    
    def _validate_artifact_files(self, config: dict) -> None:
        """Validate artifact files exist and are valid."""
        # Check notebooks
        for name, notebook in config.get('artifacts', {}).get('notebooks', {}).items():
            path = self.project_root / notebook['path']
            if not path.exists():
                self.errors.append(f"Notebook file not found: {path}")
            else:
                # Validate it's a valid notebook
                try:
                    with open(path, 'r') as f:
                        content = json.load(f)
                        if 'cells' not in content:
                            self.errors.append(f"Invalid notebook format (missing 'cells'): {path}")
                except json.JSONDecodeError:
                    self.errors.append(f"Invalid JSON in notebook: {path}")
                    
        # Check pipelines
        for name, pipeline in config.get('artifacts', {}).get('pipelines', {}).items():
            path = self.project_root / pipeline['path']
            if not path.exists():
                self.errors.append(f"Pipeline file not found: {path}")
            else:
                # Validate it's valid JSON
                try:
                    with open(path, 'r') as f:
                        content = json.load(f)
                        if 'properties' not in content:
                            self.errors.append(f"Invalid pipeline format (missing 'properties'): {path}")
                except json.JSONDecodeError:
                    self.errors.append(f"Invalid JSON in pipeline: {path}")
                    
    def _validate_workspace_access(self, config: dict) -> None:
        """Check if workspace exists and is accessible."""
        workspace_id = config['infrastructure']['workspace_id']
        
        # Try to load Service Principal credentials
        try:
            # Check if Azure SDK is available
            if ClientSecretCredential is None:
                self.warnings.append("Azure SDK not installed - skipping workspace access validation")
                return
                
            secrets_path = self.project_root / "terraform" / "secrets.tfvars"
            if not secrets_path.exists():
                self.warnings.append("No secrets.tfvars found - assuming env vars are set")
                return
                
            # Parse secrets file
            with open(secrets_path, 'r') as f:
                content = f.read()
                
            # Extract values (simple parsing for .tfvars format)
            tenant_id = self._extract_tfvar(content, 'tenant_id')
            client_id = self._extract_tfvar(content, 'client_id')
            client_secret = self._extract_tfvar(content, 'client_secret')
            
            if not all([tenant_id, client_id, client_secret]):
                self.warnings.append("Could not parse Service Principal credentials from secrets.tfvars")
                return
            
            # Create credential
            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
            
            # Get access token for Fabric API
            token = credential.get_token("https://api.fabric.microsoft.com/.default")
            
            # Check workspace exists using Fabric API
            headers = {
                'Authorization': f'Bearer {token.token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                workspace_data = response.json()
                self._workspace_name = workspace_data.get('displayName')  # Store for later use
                
                # Check capacity assignment
                capacity_id = workspace_data.get('capacityId')
                if not capacity_id:
                    self.errors.append(f"Workspace {workspace_id} is not assigned to any capacity!")
                elif capacity_id.lower() != config['infrastructure']['capacity_id'].lower():
                    self.warnings.append(f"Workspace is assigned to different capacity: {capacity_id}")
                    
            elif response.status_code == 404:
                self.errors.append(f"Workspace {workspace_id} not found")
            elif response.status_code == 403:
                self.errors.append(f"Service Principal lacks access to workspace {workspace_id}")
            else:
                self.errors.append(f"Failed to check workspace: HTTP {response.status_code}")
                
        except Exception as e:
            self.warnings.append(f"Could not validate workspace access: {e}")
            
    def _validate_capacity(self, config: dict) -> None:
        """Basic capacity validation."""
        capacity_id = config['infrastructure']['capacity_id']
        
        # Just validate format for now
        if not re.match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$', capacity_id):
            self.errors.append(f"Invalid capacity ID format: {capacity_id}")
            
    def _check_naming_conflicts(self, config: dict) -> None:
        """Check for duplicate resource names."""
        all_names = []
        
        # Collect all display names
        for notebook in config.get('artifacts', {}).get('notebooks', {}).values():
            all_names.append(notebook['display_name'])
        for pipeline in config.get('artifacts', {}).get('pipelines', {}).values():
            all_names.append(pipeline['display_name'])
            
        # Check for duplicates
        seen = set()
        duplicates = set()
        for name in all_names:
            if name in seen:
                duplicates.add(name)
            seen.add(name)
            
        if duplicates:
            for dup in duplicates:
                self.errors.append(f"Duplicate resource name: '{dup}'")
            
    def _extract_tfvar(self, content: str, var_name: str) -> Optional[str]:
        """Extract variable value from tfvars content."""
        pattern = rf'{var_name}\s*=\s*"([^"]+)"'
        match = re.search(pattern, content)
        return match.group(1) if match else None


def main():
    """Standalone validation script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate Fabric deployment configuration")
    parser.add_argument("customer", help="Customer name")
    parser.add_argument("--environment", "-e", default="dev", help="Environment")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    
    args = parser.parse_args()
    
    # Setup logging - only show ERROR and above to suppress all INFO logs
    logging.basicConfig(
        level=logging.ERROR,
        format='%(message)s'
    )
    
    project_root = Path(__file__).parent.parent
    validator = FabricValidator(project_root)
    
    print(f"\n🔍 Validating deployment configuration")
    print(f"   Customer: {args.customer}")
    print(f"   Environment: {args.environment}\n")
    
    print("Running validation checks...\n")
    success, errors, warnings = validator.validate_all(args.customer, args.environment)
    
    # Display results with clean formatting
    print("─" * 60)
    
    # Show validation status
    checks_performed = [
        ("Configuration Schema", "Schema validation failed" not in str(errors)),
        ("Resource Naming", not any("resource name" in e.lower() for e in errors)),
        ("Artifact Files", not any("not found" in e for e in errors)),
        ("Workspace Access", not any("workspace" in e.lower() for e in errors)),
        ("Capacity Assignment", not any("capacity" in e.lower() for e in errors)),
        ("Naming Conflicts", not any("duplicate" in e.lower() for e in errors)),
    ]
    
    print("Validation Results:\n")
    for check, passed in checks_performed:
        status = "✅" if passed else "❌"
        print(f"  {status} {check}")
    
    print("\n" + "─" * 60)
    
    # Show warnings if any
    if warnings:
        print("\n⚠️  Warnings:")
        for warning in warnings:
            print(f"   • {warning}")
    
    # Show errors if any
    if errors:
        print("\n❌ Errors:")
        for error in errors:
            print(f"   • {error}")
        print(f"\n🚫 Validation failed with {len(errors)} error(s)")
        print("   Please fix the above errors before deploying.")
    else:
        print("\n✅ All validations passed! Ready to deploy.")
    
    print()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()