"""
Enhanced Fabric Validator with Rich UI components
Maintains exact same validation logic as original
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.tree import Tree

try:
    import jsonschema
except ImportError:
    jsonschema = None

try:
    from azure.identity import ClientSecretCredential
    import requests
except ImportError:
    ClientSecretCredential = None
    requests = None


class FabricValidator:
    """Enhanced validator with beautiful Rich output - same logic as original"""
    
    # Resource naming rules
    NAMING_RULES = {
        'min_length': 1,
        'max_length': 128,
        'pattern': r'^[a-zA-Z0-9][a-zA-Z0-9_\-\s]*[a-zA-Z0-9]$',
        'reserved_words': ['system', 'admin', 'fabric', 'microsoft']
    }
    
    # YAML schema (same as original)
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
    
    def __init__(self, project_root: Path = None, console: Console = None):
        self.project_root = project_root or Path.cwd()
        self.console = console or Console()
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self._fabric_client = None
        self._workspace_name = None  # Store workspace name for later use
        self.validation_results = {}
        
    def validate_all(self, customer_name: str, environment: str) -> Tuple[bool, List[str], List[str]]:
        """Run all validations with beautiful progress tracking"""
        self.errors = []
        self.warnings = []
        self.validation_results = {}
        
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
        
        # Define validation checks
        checks = [
            ("Configuration Schema", lambda: self._validate_yaml_schema(config)),
            ("Resource Naming", lambda: self._validate_resource_names(config)),
            ("Artifact Files", lambda: self._validate_artifact_files(config)),
            ("Workspace Access", lambda: self._validate_workspace_access(config)),
            ("Capacity Configuration", lambda: self._validate_capacity(config)),
            ("Naming Conflicts", lambda: self._check_naming_conflicts(config))
        ]
        
        # Run validations with progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True
        ) as progress:
            
            task = progress.add_task("[cyan]Running validation checks...", total=len(checks))
            
            for check_name, check_func in checks:
                progress.update(task, description=f"[cyan]Checking {check_name}...")
                
                # Track errors before and after each check
                errors_before = len(self.errors)
                
                try:
                    check_func()
                    # Check if any errors were added during this validation
                    if len(self.errors) > errors_before:
                        self.validation_results[check_name] = "failed"
                    else:
                        self.validation_results[check_name] = "passed"
                except Exception as e:
                    self.errors.append(f"{check_name}: {str(e)}")
                    self.validation_results[check_name] = "failed"
                
                progress.advance(task)
        
        # Display detailed results
        self._display_validation_report(config, customer_name, environment)
        
        return len(self.errors) == 0, self.errors, self.warnings
    
    def _display_validation_report(self, config: dict, customer: str, environment: str):
        """Display a comprehensive validation report"""
        # Create header
        self.console.print(Panel.fit(
            f"[bold]Validation Report[/bold]\n"
            f"Customer: {customer}\n"
            f"Environment: {environment}",
            title="📋 Report",
            border_style="blue"
        ))
        
        # Show validation results table
        table = Table(title="Validation Checks", show_header=True)
        table.add_column("Check", style="cyan", width=30)
        table.add_column("Status", justify="center", width=10)
        table.add_column("Details", width=50)
        
        # Track which errors belong to which check
        error_mapping = {
            "Configuration Schema": ["Schema validation failed"],
            "Resource Naming": ["Invalid prefix", "Invalid resource name", "Resource name too"],
            "Artifact Files": ["file not found", "Invalid notebook format", "Invalid pipeline format", "Invalid JSON"],
            "Workspace Access": ["Workspace", "workspace"],
            "Capacity Configuration": ["Invalid capacity", "Capacity"],
            "Naming Conflicts": ["Duplicate resource name"]
        }
        
        for check_name, status in self.validation_results.items():
            if status == "passed":
                status_icon = "[green]✅[/green]"
                details = "[green]Passed[/green]"
            else:
                status_icon = "[red]❌[/red]"
                # Find related errors for this specific check
                related_errors = []
                for error in self.errors:
                    for keyword in error_mapping.get(check_name, []):
                        if keyword in error:
                            related_errors.append(error)
                            break
                
                if related_errors:
                    # Show first error, truncate if too long
                    first_error = related_errors[0]
                    if len(first_error) > 47:
                        details = f"[red]{first_error[:44]}...[/red]"
                    else:
                        details = f"[red]{first_error}[/red]"
                else:
                    details = "[red]Failed[/red]"
            
            table.add_row(check_name, status_icon, details)
        
        self.console.print("\n", table, "\n")
        
        # Show configuration tree only if all validations passed
        if all(status == "passed" for status in self.validation_results.values()):
            self._show_config_tree(config)
    
    def _show_config_tree(self, config: dict):
        """Show configuration in a tree format"""
        tree = Tree("[bold]Configuration Overview[/bold]")
        
        # Customer info
        customer = tree.add("[cyan]Customer[/cyan]")
        customer.add(f"Name: {config['customer']['name']}")
        customer.add(f"Prefix: {config['customer']['prefix']}")
        
        # Infrastructure
        infra = tree.add("[blue]Infrastructure[/blue]")
        infra.add(f"Workspace: ...{config['infrastructure']['workspace_id'][-12:]}")
        infra.add(f"Capacity: ...{config['infrastructure']['capacity_id'][-12:]}")
        
        # Architecture
        arch = tree.add("[green]Architecture[/green]")
        if config['architecture']['bronze_enabled']:
            arch.add("✅ Bronze Layer")
        if config['architecture']['silver_enabled']:
            arch.add("✅ Silver Layer")
        if config['architecture']['gold_enabled']:
            arch.add("✅ Gold Layer")
        
        # Artifacts
        artifacts = tree.add("[magenta]Artifacts[/magenta]")
        
        if config['artifacts'].get('notebooks'):
            notebooks = artifacts.add(f"📓 Notebooks ({len(config['artifacts']['notebooks'])})")
            for name, nb in list(config['artifacts']['notebooks'].items())[:3]:
                notebooks.add(nb['display_name'])
            if len(config['artifacts']['notebooks']) > 3:
                notebooks.add("...")
        
        if config['artifacts'].get('pipelines'):
            pipelines = artifacts.add(f"🔄 Pipelines ({len(config['artifacts']['pipelines'])})")
            for name, pl in list(config['artifacts']['pipelines'].items())[:3]:
                pipelines.add(pl['display_name'])
            if len(config['artifacts']['pipelines']) > 3:
                pipelines.add("...")
        
        self.console.print(tree)
    
    def _validate_yaml_schema(self, config: dict) -> None:
        """Validate config against JSON schema - EXACT SAME LOGIC AS ORIGINAL"""
        try:
            jsonschema.validate(config, self.CONFIG_SCHEMA)
        except jsonschema.ValidationError as e:
            self.errors.append(f"Schema validation failed: {e.message}")
            
    def _validate_resource_names(self, config: dict) -> None:
        """Validate all resource names - EXACT SAME LOGIC AS ORIGINAL"""
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
        """Validate artifact files exist and are valid - EXACT SAME LOGIC AS ORIGINAL"""
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
        """Check if workspace exists and is accessible - EXACT SAME LOGIC AS ORIGINAL"""
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
        """Basic capacity validation - EXACT SAME LOGIC AS ORIGINAL"""
        capacity_id = config['infrastructure']['capacity_id']
        
        # Just validate format for now
        if not re.match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$', capacity_id):
            self.errors.append(f"Invalid capacity ID format: {capacity_id}")
    
    def _check_naming_conflicts(self, config: dict) -> None:
        """Check for duplicate resource names - EXACT SAME LOGIC AS ORIGINAL"""
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
        """Extract variable value from tfvars content - EXACT SAME LOGIC AS ORIGINAL"""
        pattern = rf'{var_name}\s*=\s*"([^"]+)"'
        match = re.search(pattern, content)
        return match.group(1) if match else None