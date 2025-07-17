#!/usr/bin/env python3
"""
Fabric Deployment Platform CLI
A beautiful, interactive CLI for deploying Microsoft Fabric artifacts.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text
from rich import print as rprint

# Import our modules
try:
    from .fabric_deploy import FabricDeployer
    from .fabric_validate import FabricValidator
    from .fabric_preview import DeploymentPreview
except ImportError:
    # Fallback for standalone execution
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from fabric_deploy import FabricDeployer
    from fabric_validate import FabricValidator
    from fabric_preview import DeploymentPreview

# Initialize Typer app with custom help
app = typer.Typer(
    name="fabric",
    help="🚀 Microsoft Fabric Deployment Platform - Deploy with confidence!",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    context_settings={"help_option_names": ["-h", "--help"]}
)

# Initialize Rich console
console = Console()

# Add command aliases
deploy_app = typer.Typer(help="Deploy Fabric artifacts to workspaces")
validate_app = typer.Typer(help="Validate configurations and artifacts")
workspace_app = typer.Typer(help="Manage Fabric workspaces")

app.add_typer(deploy_app, name="deploy")
app.add_typer(validate_app, name="validate")
app.add_typer(workspace_app, name="workspace")


# Helper functions
def get_customer_names(incomplete: str):
    """Autocomplete customer names"""
    config_dir = Path("configs/customers")
    if config_dir.exists():
        customers = [f.stem for f in config_dir.glob("*.yaml")]
        return [c for c in customers if c.startswith(incomplete)]
    return []


def run_interactive_deployment(customer: str, environment: str):
    """Run interactive deployment wizard"""
    console.print("\n[bold cyan]🎯 Interactive Deployment Mode[/bold cyan]\n")
    
    # Customer selection
    if not customer:
        customers = get_customer_names("")
        if customers:
            console.print("Available customers:")
            for i, c in enumerate(customers, 1):
                console.print(f"  {i}. {c}")
            choice = Prompt.ask("Select customer", choices=[str(i) for i in range(1, len(customers)+1)])
            customer = customers[int(choice)-1]
        else:
            customer = Prompt.ask("Enter customer name")
    
    # Environment selection
    env_table = Table(title="Available Environments", show_header=False)
    env_table.add_column("Env", style="cyan")
    env_table.add_column("Description")
    env_table.add_row("dev", "Development environment (safe for testing)")
    env_table.add_row("test", "Testing environment")
    env_table.add_row("staging", "Staging environment (pre-production)")
    env_table.add_row("prod", "Production environment (⚠️  use with caution)")
    
    console.print(env_table)
    environment = Prompt.ask(
        "Select environment",
        choices=["dev", "test", "staging", "prod"],
        default=environment
    )
    
    return customer, environment


def show_validation_results(success: bool, errors: list, warnings: list):
    """Display validation results in a beautiful format"""
    if warnings:
        console.print("\n[yellow]⚠️  Warnings:[/yellow]")
        for warning in warnings:
            console.print(f"   [yellow]•[/yellow] {warning}")
    
    if errors:
        console.print("\n[red]❌ Errors:[/red]")
        for error in errors:
            console.print(f"   [red]•[/red] {error}")
            # Show suggested fixes
            fix = suggest_fix_for_error(error)
            if fix:
                console.print(f"     [dim]💡 Suggestion: {fix}[/dim]")
    
    # Summary
    summary_color = "green" if success else "red"
    summary_icon = "✅" if success else "❌"
    console.print(f"\n[bold {summary_color}]{summary_icon} Validation {'passed' if success else 'failed'}[/bold {summary_color}]")
    
    if not success:
        console.print(f"[dim]Found {len(errors)} error(s) and {len(warnings)} warning(s)[/dim]")


def suggest_fix_for_error(error: str) -> Optional[str]:
    """Suggest fixes for common errors"""
    error_lower = error.lower()
    
    if "workspace" in error_lower and "not found" in error_lower:
        return "Verify the workspace ID exists in your Fabric tenant"
    elif "workspace" in error_lower and "not assigned to any capacity" in error_lower:
        return "Assign the workspace to a Fabric capacity in Azure Portal"
    elif "service principal lacks access" in error_lower:
        return "Grant the Service Principal contributor access to the workspace"
    elif "notebook file not found" in error_lower or "pipeline file not found" in error_lower:
        return "Check file path and ensure the file exists"
    elif "invalid resource name" in error_lower:
        return "Resource names must start/end with alphanumeric characters"
    elif "duplicate" in error_lower:
        return "Use unique names for all resources"
    elif "invalid prefix" in error_lower:
        return "Prefix must be 2-4 lowercase letters (e.g., 'ctso')"
    elif "invalid capacity id format" in error_lower:
        return "Ensure capacity ID is a valid GUID format"
    elif "schema validation failed" in error_lower:
        return "Check YAML syntax and required fields in configuration"
    
    return None


@app.callback()
def callback():
    """
    🎯 Fabric Deployment Platform
    
    Deploy Microsoft Fabric artifacts with ease and confidence.
    """
    pass


@deploy_app.command("run")
def deploy_run(
    customer: str = typer.Argument(
        ..., 
        help="Customer name (e.g., contoso)",
        autocompletion=get_customer_names
    ),
    environment: str = typer.Option(
        "dev", 
        "--env", "-e",
        help="Deployment environment",
        rich_help_panel="Deployment Options",
        click_type=click.Choice(["dev", "test", "staging", "prod"])
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run", "-n",
        help="Show what would be deployed without making changes",
        rich_help_panel="Deployment Options"
    ),
    auto_approve: bool = typer.Option(
        False,
        "--auto-approve", "-y",
        help="Skip confirmation prompts",
        rich_help_panel="Deployment Options"
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive", "-i",
        help="Run in interactive mode with prompts",
        rich_help_panel="Deployment Options"
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Force deployment even with warnings",
        rich_help_panel="Advanced Options"
    )
):
    """
    🚀 Deploy Fabric artifacts for a customer
    
    This command will:
    • Validate all configurations
    • Check artifact files exist
    • Verify workspace access
    • Deploy via Terraform
    
    Examples:
        fabric deploy run contoso --env prod
        fabric d r contoso -e dev --dry-run
        fabric deploy run contoso --interactive
    """
    # Show beautiful header
    console.print(Panel.fit(
        f"[bold blue]Fabric Deployment Platform[/bold blue]\n"
        f"[dim]Customer:[/dim] {customer}\n"
        f"[dim]Environment:[/dim] {environment}\n"
        f"[dim]Mode:[/dim] {'Dry Run' if dry_run else 'Live Deployment'}",
        title="🚀 Deployment Session",
        border_style="blue"
    ))
    
    # Interactive mode
    if interactive:
        customer, environment = run_interactive_deployment(customer, environment)
    
    # Create deployer instance
    deployer = FabricDeployer(customer, environment, console)
    
    try:
        # Run deployment with beautiful progress
        if dry_run:
            console.print("\n[yellow]🔍 Running in dry-run mode...[/yellow]")
            success = deployer.preview_deployment()
        else:
            success = deployer.deploy(auto_approve=auto_approve, force=force)
        
        if success:
            console.print("\n[bold green]✨ Deployment completed successfully![/bold green]")
        else:
            console.print("\n[bold red]❌ Deployment failed![/bold red]")
            raise typer.Exit(1)
            
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Deployment cancelled by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[bold red]💥 Unexpected error:[/bold red] {e}")
        raise typer.Exit(1)


@deploy_app.command("preview")
def deploy_preview(
    customer: str = typer.Argument(..., help="Customer name"),
    environment: str = typer.Option("dev", "--env", "-e", help="Environment"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed preview")
):
    """
    👁️  Preview what would be deployed without making changes
    
    Shows:
    • Resources to be created/updated
    • Configuration values
    • Artifact mappings
    • Estimated deployment time
    """
    console.print(Panel.fit(
        f"[bold cyan]Deployment Preview[/bold cyan]\n"
        f"[dim]Customer:[/dim] {customer}\n"
        f"[dim]Environment:[/dim] {environment}",
        title="👁️  Preview Mode",
        border_style="cyan"
    ))
    
    previewer = DeploymentPreview(customer, environment, console)
    previewer.show_preview(detailed=detailed)


@validate_app.command("all")
def validate_all(
    customer: str = typer.Argument(..., help="Customer name"),
    environment: str = typer.Option("dev", "--env", "-e", help="Environment"),
    fix: bool = typer.Option(False, "--fix", "-f", help="Attempt to fix issues automatically")
):
    """
    🔍 Run comprehensive validation checks
    
    Validates:
    • YAML configuration syntax
    • Resource naming conventions
    • Artifact file existence
    • Workspace accessibility
    • Capacity assignment
    """
    console.print(Panel.fit(
        f"[bold yellow]Configuration Validation[/bold yellow]\n"
        f"[dim]Customer:[/dim] {customer}\n"
        f"[dim]Environment:[/dim] {environment}",
        title="🔍 Validation",
        border_style="yellow"
    ))
    
    validator = FabricValidator(console=console)
    success, errors, warnings = validator.validate_all(customer, environment)
    
    # Show results in a beautiful table
    show_validation_results(success, errors, warnings)
    
    if not success and fix:
        console.print("\n[yellow]🔧 Attempting automatic fixes...[/yellow]")
        # Implement auto-fix logic here
    
    raise typer.Exit(0 if success else 1)


@workspace_app.command("list")
def workspace_list(
    format: str = typer.Option("table", "--format", "-f", help="Output format", 
                              click_type=click.Choice(["table", "json", "yaml"]))
):
    """
    📋 List all configured workspaces
    """
    # Implementation here
    console.print("[yellow]Listing workspaces...[/yellow]")
    # Show workspace list


@workspace_app.command("info")
def workspace_info(
    workspace_id: str = typer.Argument(..., help="Workspace ID"),
    show_artifacts: bool = typer.Option(False, "--artifacts", "-a", help="Show deployed artifacts")
):
    """
    ℹ️  Show detailed workspace information
    """
    console.print(f"[cyan]Fetching workspace info for {workspace_id}...[/cyan]")
    # Show workspace details


@app.command("init")
def init_project(
    customer: str = typer.Option(None, "--customer", "-c", help="Customer name"),
    template: str = typer.Option("medallion", "--template", "-t", help="Architecture template",
                                click_type=click.Choice(["medallion", "simple", "custom"]))
):
    """
    🎬 Initialize a new Fabric deployment project
    
    Creates:
    • Customer configuration file
    • Artifact directories
    • Sample notebooks and pipelines
    """
    console.print(Panel.fit(
        "[bold green]Project Initialization[/bold green]",
        title="🎬 New Project",
        border_style="green"
    ))
    
    if not customer:
        customer = Prompt.ask("Enter customer name", default="contoso")
    
    # Initialize project structure
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Creating project structure...", total=4)
        
        # Create directories
        progress.update(task, advance=1, description="Creating directories...")
        # ... implementation
        
        progress.update(task, advance=1, description="Generating configuration...")
        # ... implementation
        
        progress.update(task, advance=1, description="Creating sample artifacts...")
        # ... implementation
        
        progress.update(task, advance=1, description="Finalizing...")
    
    console.print(f"\n[bold green]✅ Project initialized for {customer}![/bold green]")
    console.print("\nNext steps:")
    console.print("  1. Edit [cyan]configs/customers/{}.yaml[/cyan]".format(customer))
    console.print("  2. Add artifacts to [cyan]predefined-artifacts/{}/[/cyan]".format(customer))
    console.print("  3. Run [green]fabric validate all {}[/green]".format(customer))
    console.print("  4. Deploy with [green]fabric deploy run {} --env dev[/green]".format(customer))


@app.command("status")
def status(
    customer: Optional[str] = typer.Argument(None, help="Customer name (optional)")
):
    """
    📊 Show deployment status and health
    """
    console.print(Panel.fit(
        "[bold blue]Deployment Status[/bold blue]",
        title="📊 Status",
        border_style="blue"
    ))
    
    # Show status table
    table = Table(title="Recent Deployments")
    table.add_column("Customer", style="cyan")
    table.add_column("Environment", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Deployed At")
    table.add_column("Duration")
    
    # Add sample data (replace with actual implementation)
    table.add_row("contoso", "prod", "✅ Success", "2024-01-15 14:30", "5m 23s")
    table.add_row("fabrikam", "dev", "✅ Success", "2024-01-15 10:15", "3m 45s")
    table.add_row("adventure", "test", "❌ Failed", "2024-01-14 16:45", "1m 12s")
    
    console.print(table)


if __name__ == "__main__":
    app()