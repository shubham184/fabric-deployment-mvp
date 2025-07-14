#!/usr/bin/env python3
"""
Batch deployment script for Microsoft Fabric deployment platform.

This script provides specialized batch deployment capabilities with
advanced configuration options for pipeline and production use.
"""

import sys
import time
from pathlib import Path
from typing import List, Optional

import click

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.config.loader import ConfigLoader
from src.deployment.models import ExitCode, PipelineConfig
from src.deployment.orchestrator import DeploymentOrchestrator
from src.deployment.report_generator import ReportGenerator
from src.deployment.terraform_wrapper import TerraformWrapper
from src.utils.logger import get_logger, setup_logging


def load_customers_from_file(file_path: Path) -> List[str]:
    """Load customer list from file."""
    try:
        with open(file_path, 'r') as f:
            customers = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        return customers
    except Exception as e:
        raise click.ClickException(f"Failed to load customers from {file_path}: {e}")


def setup_batch_orchestrator(config_dir: str, terraform_dir: str, notebooks_dir: str, 
                            output_dir: Optional[str] = None) -> DeploymentOrchestrator:
    """Setup deployment orchestrator for batch operations."""
    configs_path = Path(config_dir)
    schemas_path = configs_path / "schemas"
    terraform_path = Path(terraform_dir)
    notebooks_path = Path(notebooks_dir)
    
    # Validate paths exist
    required_paths = [
        (configs_path, "Configuration directory"),
        (schemas_path, "Schemas directory"),
        (terraform_path, "Terraform directory"),
        (notebooks_path, "Notebooks directory")
    ]
    
    for path, description in required_paths:
        if not path.exists():
            raise click.ClickException(f"{description} not found: {path}")
    
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


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--config-dir', default='configs', help='Configuration directory')
@click.option('--terraform-dir', default='infrastructure', help='Terraform directory')
@click.option('--notebooks-dir', default='generated-notebooks', help='Generated notebooks directory')
@click.pass_context
def cli(ctx, verbose, config_dir, terraform_dir, notebooks_dir):
    """Microsoft Fabric Batch Deployment CLI."""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['config_dir'] = config_dir
    ctx.obj['terraform_dir'] = terraform_dir
    ctx.obj['notebooks_dir'] = notebooks_dir
    
    # Setup logging
    log_level = "DEBUG" if verbose else "INFO"
    setup_logging(log_level)


@cli.command()
@click.option('--customers', '-c', multiple=True, help='Customer names (multiple allowed)')
@click.option('--customers-file', '-f', type=click.Path(exists=True), 
              help='File containing customer names (one per line)')
@click.option('--environment', '-e', required=True, 
              type=click.Choice(['dev', 'test', 'prod']), help='Target environment')
@click.option('--parallel', '-p', is_flag=True, help='Deploy customers in parallel')
@click.option('--max-workers', type=int, default=3, help='Maximum parallel workers (default: 3)')
@click.option('--continue-on-error', is_flag=True, help='Continue if one customer fails')
@click.option('--dry-run', is_flag=True, help='Plan deployments without applying')
@click.option('--output-dir', help='Directory for deployment outputs')
@click.option('--delay-between', type=int, default=0, help='Delay in seconds between deployments')
@click.pass_context
def deploy(ctx, customers, customers_file, environment, parallel, max_workers, 
          continue_on_error, dry_run, output_dir, delay_between):
    """Deploy multiple customers to specified environment."""
    logger = get_logger(__name__)
    pipeline_config = PipelineConfig.from_environment()
    
    # Build customer list
    customer_list = list(customers) if customers else []
    
    if customers_file:
        file_customers = load_customers_from_file(Path(customers_file))
        customer_list.extend(file_customers)
    
    # Remove duplicates while preserving order
    customer_list = list(dict.fromkeys(customer_list))
    
    if not customer_list:
        click.echo("❌ No customers specified for batch deployment")
        click.echo("Use --customers or --customers-file to specify customers")
        sys.exit(ExitCode.CONFIGURATION_ERROR)
    
    # Set output directory
    if not output_dir:
        output_dir = str(pipeline_config.output_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        click.echo(f"🚀 Starting batch deployment")
        click.echo(f"   • Customers: {len(customer_list)}")
        click.echo(f"   • Environment: {environment}")
        click.echo(f"   • Parallel: {'Yes' if parallel else 'No'}")
        if parallel:
            click.echo(f"   • Max workers: {max_workers}")
        click.echo(f"   • Continue on error: {'Yes' if continue_on_error else 'No'}")
        if dry_run:
            click.echo(f"   • Mode: Dry run (planning only)")
        if delay_between > 0:
            click.echo(f"   • Delay between deployments: {delay_between}s")
        
        # Setup orchestrator
        orchestrator = setup_batch_orchestrator(
            ctx.obj['config_dir'],
            ctx.obj['terraform_dir'],
            ctx.obj['notebooks_dir'],
            output_dir
        )
        
        # Pre-deployment validation for all customers
        if not continue_on_error:
            click.echo(f"\n🔍 Pre-validating all customers...")
            validation_failures = []
            
            for customer in customer_list:
                try:
                    validation_result = orchestrator.validate_deployment_readiness(customer, environment)
                    if not validation_result.success:
                        validation_failures.append((customer, validation_result.errors))
                        click.echo(f"   ❌ {customer}: {'; '.join(validation_result.errors)}")
                    else:
                        click.echo(f"   ✅ {customer}: Ready")
                except Exception as e:
                    validation_failures.append((customer, [str(e)]))
                    click.echo(f"   ❌ {customer}: {e}")
            
            if validation_failures:
                click.echo(f"\n❌ Pre-validation failed for {len(validation_failures)} customers")
                click.echo("Fix validation issues or use --continue-on-error to proceed anyway")
                sys.exit(ExitCode.VALIDATION_FAILED)
            
            click.echo(f"✅ All customers passed pre-validation")
        
        # Execute batch deployment
        start_time = time.time()
        
        if parallel:
            # Use orchestrator's parallel deployment
            result = orchestrator.deploy_multiple_customers(
                customer_list, environment, parallel=True, continue_on_error=continue_on_error
            )
        else:
            # Sequential deployment with optional delays
            result = orchestrator.deploy_multiple_customers(
                customer_list, environment, parallel=False, continue_on_error=continue_on_error
            )
            
            # Add delays between deployments if requested
            if delay_between > 0 and len(customer_list) > 1:
                click.echo(f"⏱️  Adding {delay_between}s delay between deployments...")
                time.sleep(delay_between)
        
        deployment_time = time.time() - start_time
        
        # Report detailed results
        click.echo(f"\n📊 Batch Deployment Results")
        click.echo(f"   • Total time: {deployment_time:.1f}s")
        click.echo(f"   • Total customers: {result.total_customers}")
        click.echo(f"   • Successful: {result.success_count}")
        click.echo(f"   • Failed: {result.failure_count}")
        click.echo(f"   • Success rate: {result.success_count/result.total_customers*100:.1f}%")
        
        # List successful deployments
        if result.successful_deployments:
            click.echo(f"\n✅ Successful deployments:")
            for success in result.successful_deployments:
                artifacts_count = len(success.artifacts_deployed)
                click.echo(f"   • {success.customer_name}: {artifacts_count} artifacts in {success.deployment_time:.1f}s")
        
        # List failed deployments
        if result.failed_deployments:
            click.echo(f"\n❌ Failed deployments:")
            for failure in result.failed_deployments:
                click.echo(f"   • {failure.customer_name}: {'; '.join(failure.errors)}")
        
        # Generate comprehensive batch report
        report_generator = ReportGenerator(output_path / "reports")
        batch_report = report_generator.generate_batch_deployment_report(result)
        
        # Save reports in multiple formats
        saved_files = report_generator.save_report(
            batch_report, f"batch_deployment_{environment}_{int(time.time())}",
            formats=["json", "md"]
        )
        
        click.echo(f"\n📋 Batch report saved:")
        for file_path in saved_files:
            click.echo(f"   • {file_path}")
        
        # Save pipeline artifacts
        report_generator.save_pipeline_artifacts([batch_report], pipeline_config)
        
        # Exit with appropriate code
        if result.overall_success:
            click.echo(f"\n🎉 Batch deployment completed successfully!")
            sys.exit(ExitCode.SUCCESS)
        else:
            click.echo(f"\n⚠️  Batch deployment completed with failures")
            sys.exit(ExitCode.DEPLOYMENT_FAILED)
            
    except KeyboardInterrupt:
        click.echo("\n🛑 Batch deployment cancelled by user")
        sys.exit(ExitCode.UNKNOWN_ERROR)
        
    except Exception as e:
        logger.error(f"Batch deployment failed: {e}")
        click.echo(f"❌ Batch deployment failed: {e}")
        sys.exit(ExitCode.UNKNOWN_ERROR)


@cli.command()
@click.option('--customers', '-c', multiple=True, help='Customer names (multiple allowed)')
@click.option('--customers-file', '-f', type=click.Path(exists=True),
              help='File containing customer names (one per line)')
@click.option('--environment', '-e', required=True,
              type=click.Choice(['dev', 'test', 'prod']), help='Target environment')
@click.option('--output-dir', help='Directory for plan outputs')
@click.pass_context
def plan(ctx, customers, customers_file, environment, output_dir):
    """Create deployment plans for multiple customers."""
    logger = get_logger(__name__)
    pipeline_config = PipelineConfig.from_environment()
    
    # Build customer list
    customer_list = list(customers) if customers else []
    
    if customers_file:
        file_customers = load_customers_from_file(Path(customers_file))
        customer_list.extend(file_customers)
    
    customer_list = list(dict.fromkeys(customer_list))
    
    if not customer_list:
        click.echo("❌ No customers specified for batch planning")
        sys.exit(ExitCode.CONFIGURATION_ERROR)
    
    # Set output directory
    if not output_dir:
        output_dir = str(pipeline_config.output_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        click.echo(f"📋 Creating deployment plans for {len(customer_list)} customers")
        
        # Setup orchestrator
        orchestrator = setup_batch_orchestrator(
            ctx.obj['config_dir'],
            ctx.obj['terraform_dir'],
            ctx.obj['notebooks_dir'],
            output_dir
        )
        
        report_generator = ReportGenerator(output_path / "reports")
        plan_results = []
        
        for customer in customer_list:
            click.echo(f"\n📝 Planning deployment for: {customer}")
            
            try:
                plan = orchestrator.plan_deployment(customer, environment)
                
                # Display plan summary
                click.echo(f"   • Artifacts: {plan.artifacts.total_count}")
                click.echo(f"   • Estimated duration: {plan.estimated_duration:.1f}s")
                
                if plan.terraform_plan.has_changes:
                    changes = plan.terraform_plan.changes
                    click.echo(f"   • Terraform changes: +{changes.get('add', 0)} ~{changes.get('change', 0)} -{changes.get('destroy', 0)}")
                else:
                    click.echo(f"   • No Terraform changes required")
                
                # Save individual plan
                plan_report = report_generator.generate_terraform_plan_report(plan.terraform_plan)
                plan_results.append(plan_report)
                
                # Save Terraform plan file
                if plan.terraform_plan.plan_file:
                    orchestrator.terraform_wrapper.save_terraform_plan(
                        plan.terraform_plan, output_path / "terraform-plans"
                    )
                
            except Exception as e:
                click.echo(f"   ❌ Planning failed: {e}")
                plan_results.append({
                    "customer_name": customer,
                    "environment": environment,
                    "status": "failed",
                    "error": str(e)
                })
        
        # Generate summary report
        summary_report = {
            "batch_planning": {
                "environment": environment,
                "customers_planned": len(customer_list),
                "successful_plans": len([p for p in plan_results if p.get("status") != "failed"]),
                "failed_plans": len([p for p in plan_results if p.get("status") == "failed"]),
                "total_changes": sum(p.get("changes_summary", {}).get("add", 0) + 
                               p.get("changes_summary", {}).get("change", 0) + 
                               p.get("changes_summary", {}).get("destroy", 0) 
                               for p in plan_results if "changes_summary" in p)
            },
            "plans": plan_results
        }
        
        # Save summary report
        report_generator.save_report(
            summary_report, f"batch_planning_{environment}",
            formats=["json", "md"]
        )
        
        # Summary
        successful_plans = len([p for p in plan_results if p.get("status") != "failed"])
        click.echo(f"\n📊 Batch Planning Summary:")
        click.echo(f"   • Total customers: {len(customer_list)}")
        click.echo(f"   • Successful plans: {successful_plans}")
        click.echo(f"   • Failed plans: {len(customer_list) - successful_plans}")
        click.echo(f"   • Reports saved to: {output_path}")
        
        if successful_plans == len(customer_list):
            sys.exit(ExitCode.SUCCESS)
        else:
            sys.exit(ExitCode.TERRAFORM_ERROR)
            
    except Exception as e:
        logger.error(f"Batch planning failed: {e}")
        click.echo(f"❌ Batch planning failed: {e}")
        sys.exit(ExitCode.TERRAFORM_ERROR)


@cli.command()
@click.option('--customers', '-c', multiple=True, help='Customer names (multiple allowed)')
@click.option('--customers-file', '-f', type=click.Path(exists=True),
              help='File containing customer names (one per line)')
@click.option('--environment', '-e', required=True,
              type=click.Choice(['dev', 'test', 'prod']), help='Target environment')
@click.option('--output-dir', help='Directory for validation outputs')
@click.pass_context
def validate(ctx, customers, customers_file, environment, output_dir):
    """Validate deployment readiness for multiple customers."""
    logger = get_logger(__name__)
    pipeline_config = PipelineConfig.from_environment()
    
    # Build customer list
    customer_list = list(customers) if customers else []
    
    if customers_file:
        file_customers = load_customers_from_file(Path(customers_file))
        customer_list.extend(file_customers)
    
    customer_list = list(dict.fromkeys(customer_list))
    
    if not customer_list:
        # Validate all customers if none specified
        orchestrator = setup_batch_orchestrator(
            ctx.obj['config_dir'],
            ctx.obj['terraform_dir'],
            ctx.obj['notebooks_dir']
        )
        customer_list = orchestrator.config_loader.get_customer_list()
    
    # Set output directory
    if not output_dir:
        output_dir = str(pipeline_config.output_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        click.echo(f"🔍 Validating deployment readiness for {len(customer_list)} customers")
        
        # Setup orchestrator
        orchestrator = setup_batch_orchestrator(
            ctx.obj['config_dir'],
            ctx.obj['terraform_dir'],
            ctx.obj['notebooks_dir'],
            output_dir
        )
        
        validation_results = []
        
        for customer in customer_list:
            click.echo(f"\n🔍 Validating: {customer}")
            
            try:
                validation_result = orchestrator.validate_deployment_readiness(customer, environment)
                
                if validation_result.success:
                    click.echo(f"   ✅ Ready for deployment")
                    if validation_result.warnings:
                        click.echo(f"   ⚠️  {len(validation_result.warnings)} warnings")
                else:
                    click.echo(f"   ❌ Not ready: {len(validation_result.errors)} errors")
                    for error in validation_result.errors[:3]:  # Show first 3 errors
                        click.echo(f"      • {error}")
                    if len(validation_result.errors) > 3:
                        click.echo(f"      • ... and {len(validation_result.errors) - 3} more")
                
                validation_results.append({
                    "customer": customer,
                    "environment": environment,
                    "success": validation_result.success,
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings,
                    "checks_performed": validation_result.checks_performed
                })
                
            except Exception as e:
                click.echo(f"   ❌ Validation failed: {e}")
                validation_results.append({
                    "customer": customer,
                    "environment": environment,
                    "success": False,
                    "errors": [str(e)],
                    "warnings": [],
                    "checks_performed": ["validation_exception"]
                })
        
        # Generate validation report
        report_generator = ReportGenerator(output_path / "reports")
        
        successful_validations = [v for v in validation_results if v["success"]]
        failed_validations = [v for v in validation_results if not v["success"]]
        
        batch_validation_report = {
            "batch_validation": {
                "environment": environment,
                "customers_validated": len(customer_list),
                "successful_validations": len(successful_validations),
                "failed_validations": len(failed_validations),
                "success_rate": len(successful_validations) / len(customer_list) * 100 if customer_list else 0
            },
            "results": validation_results
        }
        
        # Save validation report
        report_generator.save_report(
            batch_validation_report, f"batch_validation_{environment}",
            formats=["json", "xml", "md"]
        )
        
        # Summary
        click.echo(f"\n📊 Batch Validation Summary:")
        click.echo(f"   • Total customers: {len(customer_list)}")
        click.echo(f"   • Ready for deployment: {len(successful_validations)}")
        click.echo(f"   • Not ready: {len(failed_validations)}")
        click.echo(f"   • Success rate: {len(successful_validations)/len(customer_list)*100:.1f}%")
        click.echo(f"   • Validation report saved to: {output_path}")
        
        if len(failed_validations) == 0:
            click.echo(f"\n✅ All customers ready for deployment!")
            sys.exit(ExitCode.SUCCESS)
        else:
            click.echo(f"\n❌ {len(failed_validations)} customers not ready for deployment")
            sys.exit(ExitCode.VALIDATION_FAILED)
            
    except Exception as e:
        logger.error(f"Batch validation failed: {e}")
        click.echo(f"❌ Batch validation failed: {e}")
        sys.exit(ExitCode.VALIDATION_FAILED)


@cli.command()
@click.pass_context
def list_customers(ctx):
    """List all available customers."""
    try:
        # Setup orchestrator
        orchestrator = setup_batch_orchestrator(
            ctx.obj['config_dir'],
            ctx.obj['terraform_dir'],
            ctx.obj['notebooks_dir']
        )
        
        customers = orchestrator.config_loader.get_customer_list()
        
        click.echo(f"📋 Available customers ({len(customers)}):")
        for customer in sorted(customers):
            click.echo(f"   • {customer}")
        
        if not customers:
            click.echo("No customers found in configuration directory")
            
    except Exception as e:
        click.echo(f"❌ Failed to list customers: {e}")
        sys.exit(ExitCode.CONFIGURATION_ERROR)


if __name__ == "__main__":
    cli()