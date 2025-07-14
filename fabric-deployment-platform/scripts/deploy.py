#!/usr/bin/env python3
"""
Microsoft Fabric Deployment Platform CLI.

This script provides a command-line interface for deploying Microsoft Fabric
solutions with full Azure DevOps pipeline integration and proper exit codes.
"""

import os
import sys
import time
from pathlib import Path
from typing import Optional

import click

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.config.loader import ConfigLoader
from src.deployment.artifact_manager import ArtifactManager
from src.deployment.models import ExitCode, PipelineConfig
from src.deployment.orchestrator import DeploymentOrchestrator
from src.deployment.report_generator import ReportGenerator
from src.deployment.terraform_wrapper import TerraformWrapper
from src.utils.logger import get_logger, setup_logging


def get_pipeline_config() -> PipelineConfig:
    """Get pipeline configuration from environment variables."""
    return PipelineConfig.from_environment()


def setup_orchestrator(config_dir: str, terraform_dir: str, notebooks_dir: str, 
                      output_dir: Optional[str] = None) -> DeploymentOrchestrator:
    """Setup deployment orchestrator with all dependencies."""
    configs_path = Path(config_dir)
    schemas_path = configs_path / "schemas"
    terraform_path = Path(terraform_dir)
    notebooks_path = Path(notebooks_dir)
    
    # Validate paths exist
    if not configs_path.exists():
        raise click.ClickException(f"Configuration directory not found: {configs_path}")
    if not schemas_path.exists():
        raise click.ClickException(f"Schemas directory not found: {schemas_path}")
    if not terraform_path.exists():
        raise click.ClickException(f"Terraform directory not found: {terraform_path}")
    if not notebooks_path.exists():
        raise click.ClickException(f"Notebooks directory not found: {notebooks_path}")
    
    # Initialize components
    config_loader = ConfigLoader(configs_path, schemas_path)
    terraform_wrapper = TerraformWrapper(terraform_path)
    
    output_path = Path(output_dir) if output_dir else Path("./deployment-outputs")
    
    return DeploymentOrchestrator(
        config_loader=config_loader,
        terraform_wrapper=terraform_wrapper,
        notebooks_dir=notebooks_path,
        output_dir=output_path
    )


def generate_success_artifacts(result, output_dir: Path, pipeline_config: PipelineConfig):
    """Generate pipeline artifacts for successful deployment."""
    try:
        report_generator = ReportGenerator(output_dir / "reports")
        
        # Generate deployment report
        deployment_report = report_generator.generate_deployment_report(result)
        
        # Save in multiple formats
        report_generator.save_report(
            deployment_report.to_dict(),
            f"deployment_{result.customer_name}_{result.environment}",
            formats=["json", "md"]
        )
        
        # Save pipeline artifacts
        report_generator.save_pipeline_artifacts([deployment_report.to_dict()], pipeline_config)
        
        click.echo(f"✅ Success artifacts saved to {output_dir}")
        
    except Exception as e:
        click.echo(f"⚠️  Warning: Failed to generate success artifacts: {e}", err=True)


def generate_failure_artifacts(result, output_dir: Path, pipeline_config: PipelineConfig):
    """Generate pipeline artifacts for failed deployment."""
    try:
        report_generator = ReportGenerator(output_dir / "reports")
        
        # Generate failure report
        deployment_report = report_generator.generate_deployment_report(result)
        
        # Save failure report
        report_generator.save_report(
            deployment_report.to_dict(),
            f"deployment_failure_{result.customer_name}_{result.environment}",
            formats=["json", "md"]
        )
        
        # Save pipeline artifacts
        report_generator.save_pipeline_artifacts([deployment_report.to_dict()], pipeline_config)
        
        click.echo(f"❌ Failure artifacts saved to {output_dir}")
        
    except Exception as e:
        click.echo(f"⚠️  Warning: Failed to generate failure artifacts: {e}", err=True)


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--config-dir', default='configs', help='Configuration directory')
@click.option('--terraform-dir', default='infrastructure', help='Terraform directory')
@click.option('--notebooks-dir', default='generated-notebooks', help='Generated notebooks directory')
@click.pass_context
def cli(ctx, verbose, config_dir, terraform_dir, notebooks_dir):
    """Microsoft Fabric Deployment Platform CLI."""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['config_dir'] = config_dir
    ctx.obj['terraform_dir'] = terraform_dir
    ctx.obj['notebooks_dir'] = notebooks_dir
    
    # Setup logging
    log_level = "DEBUG" if verbose else "INFO"
    setup_logging(log_level)


@cli.command()
@click.option('--customer', '-c', required=True, help='Customer name')
@click.option('--environment', '-e', required=True, 
              type=click.Choice(['dev', 'test', 'prod']), help='Target environment')
@click.option('--dry-run', is_flag=True, help='Plan deployment without applying')
@click.option('--output-dir', help='Directory for deployment outputs (pipeline artifacts)')
@click.option('--skip-validation', is_flag=True, help='Skip pre-deployment validation')
@click.pass_context
def deploy(ctx, customer, environment, dry_run, output_dir, skip_validation):
    """Deploy customer solution to specified environment."""
    logger = get_logger(__name__)
    pipeline_config = get_pipeline_config()
    
    # Override customer/environment from pipeline if available
    if pipeline_config.customer_name:
        customer = pipeline_config.customer_name
    if pipeline_config.environment and pipeline_config.environment != "dev":
        environment = pipeline_config.environment
    
    # Set output directory
    if not output_dir:
        output_dir = str(pipeline_config.output_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        click.echo(f"🚀 Starting deployment: {customer} -> {environment}")
        if dry_run:
            click.echo("📋 Dry run mode - no changes will be applied")
        
        # Setup orchestrator
        orchestrator = setup_orchestrator(
            ctx.obj['config_dir'],
            ctx.obj['terraform_dir'], 
            ctx.obj['notebooks_dir'],
            output_dir
        )
        
        # Validate deployment readiness (unless skipped)
        if not skip_validation:
            click.echo("🔍 Validating deployment readiness...")
            validation_result = orchestrator.validate_deployment_readiness(customer, environment)
            
            if not validation_result.success:
                click.echo(f"❌ Validation failed:")
                for error in validation_result.errors:
                    click.echo(f"   • {error}")
                
                # Generate validation report
                report_generator = ReportGenerator(output_path / "reports")
                validation_report = report_generator.generate_validation_report(
                    validation_result, f"pre_deployment_{customer}_{environment}"
                )
                report_generator.save_report(
                    validation_report, f"validation_failure_{customer}_{environment}",
                    formats=["json", "xml", "md"]
                )
                
                sys.exit(ExitCode.VALIDATION_FAILED)
            
            if validation_result.warnings:
                click.echo("⚠️  Validation warnings:")
                for warning in validation_result.warnings:
                    click.echo(f"   • {warning}")
        
        # Execute deployment
        start_time = time.time()
        result = orchestrator.deploy_customer(customer, environment, dry_run)
        deployment_time = time.time() - start_time
        
        # Generate artifacts based on result
        if result.success:
            click.echo(f"✅ Deployment successful in {deployment_time:.1f}s")
            click.echo(f"   • Deployed {len(result.artifacts_deployed)} artifacts")
            if result.workspace_id:
                click.echo(f"   • Workspace ID: {result.workspace_id}")
            
            generate_success_artifacts(result, output_path, pipeline_config)
            sys.exit(ExitCode.SUCCESS)
        else:
            click.echo(f"❌ Deployment failed after {deployment_time:.1f}s")
            for error in result.errors:
                click.echo(f"   • {error}")
            
            generate_failure_artifacts(result, output_path, pipeline_config)
            sys.exit(ExitCode.DEPLOYMENT_FAILED)
            
    except KeyboardInterrupt:
        click.echo("\n🛑 Deployment cancelled by user")
        sys.exit(ExitCode.UNKNOWN_ERROR)
        
    except Exception as e:
        logger.error(f"Deployment failed with exception: {e}")
        click.echo(f"❌ Deployment failed: {e}")
        
        # Determine appropriate exit code
        if "validation" in str(e).lower():
            sys.exit(ExitCode.VALIDATION_FAILED)
        elif "terraform" in str(e).lower():
            sys.exit(ExitCode.TERRAFORM_ERROR)
        elif "configuration" in str(e).lower():
            sys.exit(ExitCode.CONFIGURATION_ERROR)
        elif "artifact" in str(e).lower():
            sys.exit(ExitCode.ARTIFACT_ERROR)
        else:
            sys.exit(ExitCode.UNKNOWN_ERROR)


@cli.command()
@click.option('--customers', '-c', multiple=True, help='Customer names (multiple allowed)')
@click.option('--environment', '-e', required=True, 
              type=click.Choice(['dev', 'test', 'prod']), help='Target environment')
@click.option('--parallel', is_flag=True, help='Deploy customers in parallel')
@click.option('--continue-on-error', is_flag=True, help='Continue if one customer fails')
@click.option('--output-dir', help='Directory for deployment outputs')
@click.pass_context
def batch_deploy(ctx, customers, environment, parallel, continue_on_error, output_dir):
    """Deploy multiple customers to environment."""
    logger = get_logger(__name__)
    pipeline_config = get_pipeline_config()
    
    # Set output directory
    if not output_dir:
        output_dir = str(pipeline_config.output_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    if not customers:
        click.echo("❌ No customers specified for batch deployment")
        sys.exit(ExitCode.CONFIGURATION_ERROR)
    
    try:
        click.echo(f"🚀 Starting batch deployment: {len(customers)} customers -> {environment}")
        if parallel:
            click.echo("⚡ Parallel deployment mode enabled")
        if continue_on_error:
            click.echo("🔄 Continue-on-error mode enabled")
        
        # Setup orchestrator
        orchestrator = setup_orchestrator(
            ctx.obj['config_dir'],
            ctx.obj['terraform_dir'],
            ctx.obj['notebooks_dir'],
            output_dir
        )
        
        # Execute batch deployment
        start_time = time.time()
        result = orchestrator.deploy_multiple_customers(
            list(customers), environment, parallel, continue_on_error
        )
        deployment_time = time.time() - start_time
        
        # Report results
        click.echo(f"\n📊 Batch deployment completed in {deployment_time:.1f}s")
        click.echo(f"   • Total customers: {result.total_customers}")
        click.echo(f"   • Successful: {result.success_count}")
        click.echo(f"   • Failed: {result.failure_count}")
        click.echo(f"   • Success rate: {result.success_count/result.total_customers*100:.1f}%")
        
        # Generate batch report
        report_generator = ReportGenerator(output_path / "reports")
        batch_report = report_generator.generate_batch_deployment_report(result)
        report_generator.save_report(
            batch_report, f"batch_deployment_{environment}",
            formats=["json", "md"]
        )
        
        # List failed customers
        if result.failed_deployments:
            click.echo("\n❌ Failed deployments:")
            for failed in result.failed_deployments:
                click.echo(f"   • {failed.customer_name}: {'; '.join(failed.errors)}")
        
        # Exit with appropriate code
        if result.overall_success:
            sys.exit(ExitCode.SUCCESS)
        else:
            sys.exit(ExitCode.DEPLOYMENT_FAILED)
            
    except Exception as e:
        logger.error(f"Batch deployment failed: {e}")
        click.echo(f"❌ Batch deployment failed: {e}")
        sys.exit(ExitCode.UNKNOWN_ERROR)


@cli.command()
@click.option('--customer', '-c', required=True, help='Customer name')
@click.option('--environment', '-e', required=True,
              type=click.Choice(['dev', 'test', 'prod']), help='Target environment')
@click.option('--output-dir', help='Directory for deployment outputs')
@click.pass_context
def destroy(ctx, customer, environment, output_dir):
    """Destroy customer deployment."""
    logger = get_logger(__name__)
    pipeline_config = get_pipeline_config()
    
    # Set output directory
    if not output_dir:
        output_dir = str(pipeline_config.output_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        click.echo(f"🗑️  Starting destruction: {customer} in {environment}")
        
        # Confirm destruction (unless in pipeline)
        if not pipeline_config.build_id:  # Not in pipeline
            if not click.confirm(f"Are you sure you want to destroy {customer} in {environment}?"):
                click.echo("Destruction cancelled")
                sys.exit(ExitCode.SUCCESS)
        
        # Setup orchestrator
        orchestrator = setup_orchestrator(
            ctx.obj['config_dir'],
            ctx.obj['terraform_dir'],
            ctx.obj['notebooks_dir'],
            output_dir
        )
        
        # Execute destruction
        start_time = time.time()
        result = orchestrator.destroy_deployment(customer, environment)
        destruction_time = time.time() - start_time
        
        # Report results
        if result.success:
            click.echo(f"✅ Destruction successful in {destruction_time:.1f}s")
            sys.exit(ExitCode.SUCCESS)
        else:
            click.echo(f"❌ Destruction failed after {destruction_time:.1f}s")
            for error in result.errors:
                click.echo(f"   • {error}")
            sys.exit(ExitCode.DEPLOYMENT_FAILED)
            
    except Exception as e:
        logger.error(f"Destruction failed: {e}")
        click.echo(f"❌ Destruction failed: {e}")
        sys.exit(ExitCode.TERRAFORM_ERROR)


@cli.command()
@click.option('--customer', '-c', help='Specific customer (optional)')
@click.option('--environment', '-e', help='Specific environment (optional)')
@click.pass_context
def status(ctx, customer, environment):
    """Get deployment status."""
    logger = get_logger(__name__)
    
    try:
        # Setup orchestrator
        orchestrator = setup_orchestrator(
            ctx.obj['config_dir'],
            ctx.obj['terraform_dir'],
            ctx.obj['notebooks_dir']
        )
        
        if customer and environment:
            # Get status for specific customer/environment
            status = orchestrator.get_deployment_status(customer, environment)
            click.echo(f"Status for {customer}/{environment}: {status.value}")
        
        elif customer:
            # Get status for all environments of a customer
            environments = ["dev", "test", "prod"]
            click.echo(f"Status for customer '{customer}':")
            for env in environments:
                try:
                    status = orchestrator.get_deployment_status(customer, env)
                    click.echo(f"  {env}: {status.value}")
                except Exception:
                    click.echo(f"  {env}: unknown")
        
        else:
            # Get available customers
            customers = orchestrator.config_loader.get_customer_list()
            click.echo(f"Available customers: {', '.join(customers)}")
            click.echo("Use --customer to get detailed status")
            
        sys.exit(ExitCode.SUCCESS)
        
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        click.echo(f"❌ Status check failed: {e}")
        sys.exit(ExitCode.UNKNOWN_ERROR)


@cli.command()
@click.option('--customer', '-c', required=True, help='Customer name')
@click.option('--environment', '-e', required=True,
              type=click.Choice(['dev', 'test', 'prod']), help='Target environment')
@click.option('--output-dir', help='Directory for plan outputs')
@click.pass_context
def plan(ctx, customer, environment, output_dir):
    """Create deployment plan without executing."""
    logger = get_logger(__name__)
    pipeline_config = get_pipeline_config()
    
    # Set output directory
    if not output_dir:
        output_dir = str(pipeline_config.output_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        click.echo(f"📋 Creating deployment plan: {customer} -> {environment}")
        
        # Setup orchestrator
        orchestrator = setup_orchestrator(
            ctx.obj['config_dir'],
            ctx.obj['terraform_dir'],
            ctx.obj['notebooks_dir'],
            output_dir
        )
        
        # Create plan
        plan = orchestrator.plan_deployment(customer, environment)
        
        # Display plan summary
        click.echo(f"\n📊 Deployment Plan Summary:")
        click.echo(f"   • Customer: {plan.customer_name}")
        click.echo(f"   • Environment: {plan.environment}")
        click.echo(f"   • Total artifacts: {plan.artifacts.total_count}")
        click.echo(f"   • Estimated duration: {plan.estimated_duration:.1f}s")
        
        # Terraform changes
        tf_plan = plan.terraform_plan
        if tf_plan.has_changes:
            click.echo(f"\n🔧 Terraform Changes:")
            click.echo(f"   • Resources to add: {tf_plan.changes.get('add', 0)}")
            click.echo(f"   • Resources to change: {tf_plan.changes.get('change', 0)}")
            click.echo(f"   • Resources to destroy: {tf_plan.changes.get('destroy', 0)}")
        else:
            click.echo(f"\n✅ No Terraform changes required")
        
        # Save plan artifacts
        report_generator = ReportGenerator(output_path / "reports")
        plan_report = report_generator.generate_terraform_plan_report(tf_plan)
        
        # Save plan to output directory
        if tf_plan.plan_file:
            saved_plan = orchestrator.terraform_wrapper.save_terraform_plan(tf_plan, output_path / "terraform-plans")
            click.echo(f"\n💾 Plan saved to: {saved_plan}")
        
        report_generator.save_report(
            plan_report, f"deployment_plan_{customer}_{environment}",
            formats=["json", "md"]
        )
        
        sys.exit(ExitCode.SUCCESS)
        
    except Exception as e:
        logger.error(f"Planning failed: {e}")
        click.echo(f"❌ Planning failed: {e}")
        sys.exit(ExitCode.TERRAFORM_ERROR)


if __name__ == "__main__":
    cli()