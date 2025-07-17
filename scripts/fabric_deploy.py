"""
Enhanced Fabric Deployer with Rich UI components
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

try:
    from .fabric_validate import FabricValidator
except ImportError:
    # Fallback for standalone execution
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from fabric_validate import FabricValidator


class FabricDeployer:
    """Enhanced deployer with beautiful Rich UI"""
    
    def __init__(self, customer_name: str, environment: str, console: Console):
        self.customer_name = customer_name
        self.environment = environment
        self.console = console
        self.project_root = Path(__file__).parent.parent
        self.terraform_dir = self.project_root / "terraform"
        self.validator = FabricValidator(console=console)
        self.deployment_steps = []
        
    def deploy(self, auto_approve: bool = False, force: bool = False) -> bool:
        """Main deployment with rich progress tracking"""
        start_time = time.time()
        
        # Define deployment steps
        steps = [
            ("🔍 Validating configuration", self._validate_step),
            ("📋 Loading configuration", self._load_config_step),
            ("🔧 Preparing Terraform", self._prepare_terraform_step),
            ("🚀 Running Terraform", self._run_terraform_step),
            ("📊 Gathering results", self._gather_results_step)
        ]
        
        # Create progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
            transient=True
        ) as progress:
            
            main_task = progress.add_task(
                f"[cyan]Deploying {self.customer_name} to {self.environment}...", 
                total=len(steps)
            )
            
            for step_name, step_func in steps:
                progress.update(main_task, description=f"[cyan]{step_name}")
                
                try:
                    result = step_func(auto_approve=auto_approve, force=force)
                    if not result:
                        self._show_error(f"Failed at step: {step_name}")
                        return False
                    progress.advance(main_task)
                    
                except Exception as e:
                    self._show_error(f"Error in {step_name}: {str(e)}")
                    return False
        
        # Show deployment summary
        duration = time.time() - start_time
        self._show_deployment_summary(duration)
        
        return True
    
    def preview_deployment(self) -> bool:
        """Show what would be deployed"""
        config = self.load_config()
        tf_vars = self.prepare_terraform_vars(config)
        
        # Create preview panel
        preview = Panel.fit(
            self._create_preview_tree(config, tf_vars),
            title="[bold cyan]Deployment Preview[/bold cyan]",
            border_style="cyan"
        )
        
        self.console.print(preview)
        
        # Show artifact details
        self._show_artifact_preview(config)
        
        return True
    
    def _validate_step(self, **kwargs) -> bool:
        """Validation step with progress"""
        force = kwargs.get('force', False)
        
        success, errors, warnings = self.validator.validate_all(
            self.customer_name, 
            self.environment
        )
        
        if not success and not force:
            return False
        elif not success and force:
            self.console.print("[yellow]⚠️  Continuing with errors due to --force flag[/yellow]")
            
        return True
    
    def _load_config_step(self, **kwargs) -> dict:
        """Load configuration with progress"""
        config = self.load_config()
        self.config = config
        return config
    
    def _prepare_terraform_step(self, **kwargs) -> bool:
        """Prepare Terraform with progress"""
        tf_vars = self.prepare_terraform_vars(self.config)
        
        # Write tfvars file
        tfvars_path = self.terraform_dir / f"{self.customer_name}-{self.environment}.auto.tfvars.json"
        with open(tfvars_path, 'w') as f:
            json.dump(tf_vars, f, indent=2)
        
        self.tf_vars = tf_vars
        return True
    
    def _run_terraform_step(self, **kwargs) -> bool:
        """Run Terraform with live output"""
        auto_approve = kwargs.get('auto_approve', False)
        
        os.chdir(self.terraform_dir)
        
        # Check for secrets file
        secrets_file = self.terraform_dir / "secrets.tfvars"
        var_file_args = ["-var-file=secrets.tfvars"] if secrets_file.exists() else []
        
        # Initialize Terraform
        self.console.print("\n[dim]Initializing Terraform...[/dim]")
        if not self._run_terraform_command(["terraform", "init"], show_output=False):
            return False
        
        # Plan
        self.console.print("[dim]Creating execution plan...[/dim]")
        plan_cmd = ["terraform", "plan", "-out=tfplan"] + var_file_args
        if not self._run_terraform_command(plan_cmd, show_output=False):
            return False
        
        # Show plan summary
        self._show_terraform_plan_summary()
        
        # Confirm deployment
        if not auto_approve:
            if not Confirm.ask("\n[bold yellow]Proceed with deployment?[/bold yellow]"):
                self.console.print("[yellow]Deployment cancelled[/yellow]")
                return False
        
        # Apply
        self.console.print("\n[dim]Applying changes...[/dim]")
        apply_cmd = ["terraform", "apply", "tfplan"]
        
        # Run apply with live output
        with Live(console=self.console, refresh_per_second=4) as live:
            process = subprocess.Popen(
                apply_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            output_lines = []
            for line in process.stdout:
                output_lines.append(line.strip())
                # Show last 10 lines
                display_lines = output_lines[-10:]
                live.update(
                    Panel(
                        "\n".join(display_lines),
                        title="[cyan]Terraform Apply Progress[/cyan]",
                        border_style="cyan"
                    )
                )
            
            process.wait()
            
        return process.returncode == 0
    
    def _gather_results_step(self, **kwargs) -> bool:
        """Gather deployment results"""
        # Get Terraform outputs
        result = subprocess.run(
            ["terraform", "output", "-json"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            self.outputs = json.loads(result.stdout)
        
        return True
    
    def _show_terraform_plan_summary(self):
        """Show a summary of the Terraform plan"""
        # Get plan details
        result = subprocess.run(
            ["terraform", "show", "-json", "tfplan"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            plan = json.loads(result.stdout)
            
            # Count changes
            to_add = len([c for c in plan.get('resource_changes', []) 
                         if c['change']['actions'] == ['create']])
            to_change = len([c for c in plan.get('resource_changes', []) 
                           if c['change']['actions'] == ['update']])
            to_delete = len([c for c in plan.get('resource_changes', []) 
                           if c['change']['actions'] == ['delete']])
            
            # Create summary table
            table = Table(title="Terraform Plan Summary", show_header=False)
            table.add_column("Action", style="bold")
            table.add_column("Count", justify="right")
            
            if to_add > 0:
                table.add_row("[green]To add[/green]", f"[green]{to_add}[/green]")
            if to_change > 0:
                table.add_row("[yellow]To change[/yellow]", f"[yellow]{to_change}[/yellow]")
            if to_delete > 0:
                table.add_row("[red]To destroy[/red]", f"[red]{to_delete}[/red]")
            
            self.console.print("\n", table, "\n")
    
    def _create_preview_tree(self, config: dict, tf_vars: dict) -> Tree:
        """Create a tree view of what will be deployed"""
        tree = Tree(f"[bold]{self.customer_name}[/bold] ({self.environment})")
        
        # Infrastructure
        infra = tree.add("[cyan]Infrastructure[/cyan]")
        infra.add(f"Workspace: {config['infrastructure']['workspace_id'][:8]}...")
        infra.add(f"Capacity: {config['infrastructure']['capacity_id'][:8]}...")
        
        # Lakehouses
        lakehouses = tree.add("[blue]Lakehouses[/blue]")
        if config['architecture']['bronze_enabled']:
            lakehouses.add("🥉 Bronze Lakehouse")
        if config['architecture']['silver_enabled']:
            lakehouses.add("🥈 Silver Lakehouse")
        if config['architecture']['gold_enabled']:
            lakehouses.add("🥇 Gold Lakehouse")
        
        # Notebooks
        if config['artifacts'].get('notebooks'):
            notebooks = tree.add(f"[green]Notebooks ({len(config['artifacts']['notebooks'])})[/green]")
            for name, nb in config['artifacts']['notebooks'].items():
                notebooks.add(f"📓 {nb['display_name']}")
        
        # Pipelines
        if config['artifacts'].get('pipelines'):
            pipelines = tree.add(f"[magenta]Pipelines ({len(config['artifacts']['pipelines'])})[/magenta]")
            for name, pl in config['artifacts']['pipelines'].items():
                pipelines.add(f"🔄 {pl['display_name']}")
        
        return tree
    
    def _show_artifact_preview(self, config: dict):
        """Show detailed artifact preview"""
        # Create artifact table
        table = Table(title="Artifact Details")
        table.add_column("Type", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Source Path")
        table.add_column("Size", justify="right")
        
        # Add notebooks
        for name, nb in config.get('artifacts', {}).get('notebooks', {}).items():
            path = self.project_root / nb['path']
            size = path.stat().st_size if path.exists() else 0
            table.add_row(
                "📓 Notebook",
                nb['display_name'],
                str(path.relative_to(self.project_root)),
                f"{size:,} bytes"
            )
        
        # Add pipelines
        for name, pl in config.get('artifacts', {}).get('pipelines', {}).items():
            path = self.project_root / pl['path']
            size = path.stat().st_size if path.exists() else 0
            table.add_row(
                "🔄 Pipeline",
                pl['display_name'],
                str(path.relative_to(self.project_root)),
                f"{size:,} bytes"
            )
        
        self.console.print("\n", table)
    
    def _show_deployment_summary(self, duration: float):
        """Show beautiful deployment summary"""
        if hasattr(self, 'outputs') and self.outputs:
            summary = self.outputs.get('deployment_summary', {}).get('value', {})
            
            # Create summary panel
            content = f"""[bold green]✨ Deployment Successful![/bold green]

[bold]Customer:[/bold] {summary.get('customer', 'N/A')}
[bold]Environment:[/bold] {summary.get('environment', 'N/A')}
[bold]Duration:[/bold] {duration:.1f} seconds

[bold cyan]Resources Created:[/bold cyan]
  • Lakehouses: {summary.get('lakehouses_created', 0)}
  • Notebooks: {summary.get('notebooks_deployed', 0)}
  • Pipelines: {summary.get('pipelines_deployed', 0)}

[bold]Workspace:[/bold] {summary.get('workspace_id', 'N/A')}
"""
            
            panel = Panel(
                content,
                title="[bold green]Deployment Complete[/bold green]",
                border_style="green",
                expand=False
            )
            
            self.console.print("\n", panel)
    
    def _show_error(self, message: str):
        """Show error in a nice format"""
        self.console.print(Panel(
            f"[bold red]❌ {message}[/bold red]",
            border_style="red",
            expand=False
        ))
    
    def _run_terraform_command(self, cmd: list, show_output: bool = True) -> bool:
        """Run a terraform command"""
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if show_output and result.stdout:
            self.console.print(result.stdout)
        
        if result.returncode != 0:
            if result.stderr:
                self.console.print(f"[red]Error: {result.stderr}[/red]")
            return False
        
        return True
    
    def load_config(self) -> dict:
        """Load customer configuration"""
        config_path = self.project_root / "configs" / "customers" / f"{self.customer_name}.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Customer config not found: {config_path}")
        
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def prepare_terraform_vars(self, config: dict) -> dict:
        """Prepare Terraform variables"""
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
            "notebooks": config["artifacts"].get("notebooks", {}),
            "pipelines": config["artifacts"].get("pipelines", {})
        }
        
        tf_vars.update(env_config)
        return tf_vars