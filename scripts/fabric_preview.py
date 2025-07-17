"""
Deployment Preview module for showing what will be deployed
"""

import json
from pathlib import Path
from typing import Dict, List

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree
from rich.columns import Columns
from rich.text import Text


class DeploymentPreview:
    """Show detailed preview of deployment"""
    
    def __init__(self, customer_name: str, environment: str, console: Console):
        self.customer_name = customer_name
        self.environment = environment
        self.console = console
        self.project_root = Path(__file__).parent.parent
        
    def show_preview(self, detailed: bool = False):
        """Show deployment preview"""
        # Load configuration
        config = self._load_config()
        
        # Show overview
        self._show_overview(config)
        
        # Show resources to be created
        self._show_resources_preview(config)
        
        # Show artifact mapping
        self._show_artifact_mapping(config)
        
        if detailed:
            # Show detailed artifact contents
            self._show_detailed_artifacts(config)
            
            # Show Terraform variables
            self._show_terraform_vars(config)
        
        # Show deployment estimate
        self._show_deployment_estimate(config)
    
    def _load_config(self) -> dict:
        """Load customer configuration"""
        config_path = self.project_root / "configs" / "customers" / f"{self.customer_name}.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Customer config not found: {config_path}")
        
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _show_overview(self, config: dict):
        """Show deployment overview"""
        overview = f"""[bold cyan]Deployment Overview[/bold cyan]

[bold]Customer:[/bold] {config['customer']['name']}
[bold]Prefix:[/bold] {config['customer']['prefix']}
[bold]Environment:[/bold] {self.environment}

[bold]Target Infrastructure:[/bold]
  • Workspace: {config['infrastructure']['workspace_id']}
  • Capacity: {config['infrastructure']['capacity_id']}

[bold]Architecture:[/bold]
  • Bronze Layer: {'✅ Enabled' if config['architecture']['bronze_enabled'] else '❌ Disabled'}
  • Silver Layer: {'✅ Enabled' if config['architecture']['silver_enabled'] else '❌ Disabled'}
  • Gold Layer: {'✅ Enabled' if config['architecture']['gold_enabled'] else '❌ Disabled'}
"""
        
        self.console.print(Panel(
            overview,
            title="📋 Overview",
            border_style="cyan"
        ))
    
    def _show_resources_preview(self, config: dict):
        """Show resources that will be created"""
        # Create resource tree
        tree = Tree("[bold]Resources to be Created/Updated[/bold]")
        
        # Lakehouses
        lakehouses = tree.add("[blue]Lakehouses[/blue]")
        prefix = config['customer']['prefix']
        
        if config['architecture']['bronze_enabled']:
            bronze = lakehouses.add(f"🥉 {prefix}_bronze_lakehouse")
            bronze.add("[dim]Type: fabric_lakehouse[/dim]")
            bronze.add("[dim]Schemas: Enabled[/dim]")
        
        if config['architecture']['silver_enabled']:
            silver = lakehouses.add(f"🥈 {prefix}_silver_lakehouse")
            silver.add("[dim]Type: fabric_lakehouse[/dim]")
            silver.add("[dim]Schemas: Enabled[/dim]")
        
        if config['architecture']['gold_enabled']:
            gold = lakehouses.add(f"🥇 {prefix}_gold_lakehouse")
            gold.add("[dim]Type: fabric_lakehouse[/dim]")
            gold.add("[dim]Schemas: Enabled[/dim]")
        
        # Notebooks
        if config['artifacts'].get('notebooks'):
            notebooks = tree.add(f"[green]Notebooks ({len(config['artifacts']['notebooks'])})[/green]")
            for name, nb in config['artifacts']['notebooks'].items():
                nb_node = notebooks.add(f"📓 {nb['display_name']}")
                nb_node.add(f"[dim]Key: {name}[/dim]")
                nb_node.add(f"[dim]Format: ipynb[/dim]")
        
        # Pipelines
        if config['artifacts'].get('pipelines'):
            pipelines = tree.add(f"[magenta]Pipelines ({len(config['artifacts']['pipelines'])})[/magenta]")
            for name, pl in config['artifacts']['pipelines'].items():
                pl_node = pipelines.add(f"🔄 {pl['display_name']}")
                pl_node.add(f"[dim]Key: {name}[/dim]")
                pl_node.add(f"[dim]Format: Default[/dim]")
        
        self.console.print("\n", tree, "\n")
    
    def _show_artifact_mapping(self, config: dict):
        """Show artifact file mapping"""
        table = Table(title="Artifact File Mapping")
        table.add_column("Resource Name", style="cyan")
        table.add_column("Source File", style="green")
        table.add_column("Exists", justify="center")
        table.add_column("Size", justify="right")
        
        # Add notebooks
        for name, nb in config.get('artifacts', {}).get('notebooks', {}).items():
            path = self.project_root / nb['path']
            exists = "✅" if path.exists() else "❌"
            size = f"{path.stat().st_size:,} B" if path.exists() else "N/A"
            
            table.add_row(
                nb['display_name'],
                str(path.relative_to(self.project_root)),
                exists,
                size
            )
        
        # Add pipelines
        for name, pl in config.get('artifacts', {}).get('pipelines', {}).items():
            path = self.project_root / pl['path']
            exists = "✅" if path.exists() else "❌"
            size = f"{path.stat().st_size:,} B" if path.exists() else "N/A"
            
            table.add_row(
                pl['display_name'],
                str(path.relative_to(self.project_root)),
                exists,
                size
            )
        
        self.console.print(table, "\n")
    
    def _show_detailed_artifacts(self, config: dict):
        """Show detailed artifact contents preview"""
        self.console.print(Panel.fit(
            "[bold]Detailed Artifact Preview[/bold]",
            border_style="yellow"
        ))
        
        # Show first notebook content preview
        notebooks = config.get('artifacts', {}).get('notebooks', {})
        if notebooks:
            first_nb = list(notebooks.values())[0]
            path = self.project_root / first_nb['path']
            
            if path.exists():
                with open(path, 'r') as f:
                    content = json.load(f)
                
                # Show first cell
                if content.get('cells'):
                    first_cell = content['cells'][0]
                    cell_content = ''.join(first_cell.get('source', []))[:200] + "..."
                    
                    self.console.print(f"\n[bold]Sample from '{first_nb['display_name']}':[/bold]")
                    self.console.print(Panel(
                        Syntax(cell_content, "python", theme="monokai", line_numbers=False),
                        border_style="dim"
                    ))
    
    def _show_terraform_vars(self, config: dict):
        """Show Terraform variables that will be used"""
        env_config = config.get("environments", {}).get(self.environment, {})
        
        tf_vars = {
            "customer_name": config["customer"]["name"],
            "customer_prefix": config["customer"]["prefix"],
            "workspace_id": config["infrastructure"]["workspace_id"],
            "capacity_id": config["infrastructure"]["capacity_id"],
            "environment": self.environment,
            "bronze_enabled": config["architecture"]["bronze_enabled"],
            "silver_enabled": config["architecture"]["silver_enabled"],
            "gold_enabled": config["architecture"]["gold_enabled"],
        }
        
        tf_vars.update(env_config)
        
        # Show as formatted JSON
        self.console.print("\n[bold]Terraform Variables:[/bold]")
        self.console.print(Panel(
            Syntax(json.dumps(tf_vars, indent=2), "json", theme="monokai"),
            border_style="dim"
        ))
    
    def _show_deployment_estimate(self, config: dict):
        """Show deployment time estimate"""
        # Calculate estimates
        num_lakehouses = sum([
            config['architecture']['bronze_enabled'],
            config['architecture']['silver_enabled'],
            config['architecture']['gold_enabled']
        ])
        num_notebooks = len(config.get('artifacts', {}).get('notebooks', {}))
        num_pipelines = len(config.get('artifacts', {}).get('pipelines', {}))
        
        # Rough estimates (seconds)
        lakehouse_time = num_lakehouses * 30
        notebook_time = num_notebooks * 15
        pipeline_time = num_pipelines * 20
        overhead_time = 60  # Terraform init, plan, etc.
        
        total_time = lakehouse_time + notebook_time + pipeline_time + overhead_time
        
        # Create estimate panel
        estimate = f"""[bold yellow]Deployment Time Estimate[/bold yellow]

[bold]Resources:[/bold]
  • {num_lakehouses} Lakehouses × 30s = {lakehouse_time}s
  • {num_notebooks} Notebooks × 15s = {notebook_time}s
  • {num_pipelines} Pipelines × 20s = {pipeline_time}s
  • Terraform overhead = {overhead_time}s

[bold]Total Estimated Time:[/bold] {total_time // 60}m {total_time % 60}s

[dim]Note: Actual times may vary based on Fabric API response times[/dim]
"""
        
        self.console.print(Panel(
            estimate,
            title="⏱️  Time Estimate",
            border_style="yellow"
        ))