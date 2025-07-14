#!/usr/bin/env python3
"""
Enhanced validation script for Microsoft Fabric deployment platform.

This script provides comprehensive validation including configuration,
artifacts, prerequisites, and deployment readiness checks.
"""

import sys
from pathlib import Path

import click

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.config.loader import ConfigLoader
from src.deployment.models import ExitCode
from src.deployment.orchestrator import DeploymentOrchestrator
from src.deployment.report_generator import ReportGenerator
from src.deployment.terraform_wrapper import TerraformWrapper
from src.utils.logger import get_logger, setup_logging


def setup_validation_system(config_dir: str, terraform_dir: str, notebooks_dir: str):
    """Setup validation system components."""
    configs_path = Path(config_dir)
    schemas_path = configs_path / "schemas"
    terraform_path = Path(terraform_dir)
    notebooks_path = Path(notebooks_dir)
    
    # Initialize components
    config_loader = ConfigLoader(configs_path, schemas_path)
    terraform_wrapper = TerraformWrapper(terraform_path)
    
    return DeploymentOrchestrator(
        config_loader=config_loader,
        terraform_wrapper=terraform_wrapper,
        notebooks_dir=notebooks_path
    )


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--config-dir', default='configs', help='Configuration directory')
@click.option('--terraform-dir', default='infrastructure', help='Terraform directory')
@click.option('--notebooks-dir', default='generated-notebooks', help='Generated notebooks directory')
@click.pass_context
def cli(ctx, verbose, config_dir, terraform_dir, notebooks_dir):
    """Microsoft Fabric Deployment Platform Validation CLI."""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['config_dir'] = config_dir
    ctx.obj['terraform_dir'] = terraform_dir
    ctx.obj['notebooks_dir'] = notebooks_dir
    
    # Setup logging
    log_level = "DEBUG" if verbose else "INFO"
    setup_logging(log_level)


@cli.command()
@click.option('--customer', '-c', help='Specific customer to validate (optional)')
@click.option('--environment', '-e', help='Specific environment to validate (optional)')
@click.option('--output-dir', default='validation-outputs', help='Directory for validation reports')
@click.pass_context
def config(ctx, customer, environment, output_dir):
    """Validate configuration files."""
    logger = get_logger(__name__)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        click.echo("🔍 Validating configuration files...")
        
        # Setup validation system
        orchestrator = setup_validation_system(
            ctx.obj['config_dir'],
            ctx.obj['terraform_dir'],
            ctx.obj['notebooks_dir']
        )
        
        validation_results = []
        customers_to_validate = []
        
        if customer:
            customers_to_validate.append(customer)
        else:
            customers_to_validate = orchestrator.config_loader.get_customer_list()
            click.echo(f"Validating {len(customers_to_validate)} customers...")
        
        for customer_name in customers_to_validate:
            click.echo(f"\n📁 Validating customer: {customer_name}")
            
            try:
                # Validate customer base configuration
                customer_config = orchestrator.config_loader.load_customer_base(customer_name)
                click.echo(f"   ✅ Base configuration valid")
                
                # Validate environments
                environments_to_check = [environment] if environment else ["dev", "test", "prod"]
                
                for env in environments_to_check:
                    try:
                        env_config = orchestrator.config_loader.load_environment_override(customer_name, env)
                        merged_config = orchestrator.config_loader.load_merged_config(customer_name, env)
                        click.echo(f"   ✅ Environment '{env}' configuration valid")
                        
                        # Validate template variables can be prepared
                        template_vars = orchestrator.config_loader.prepare_template_variables(merged_config, env)
                        click.echo(f"   ✅ Template variables for '{env}' prepared successfully")
                        
                    except Exception as e:
                        click.echo(f"   ❌ Environment '{env}' validation failed: {e}")
                        validation_results.append({
                            "customer": customer_name,
                            "environment": env,
                            "status": "failed",
                            "error": str(e)
                        })
                        
            except Exception as e:
                click.echo(f"   ❌ Customer validation failed: {e}")
                validation_results.append({
                    "customer": customer_name,
                    "environment": "all",
                    "status": "failed", 
                    "error": str(e)
                })
        
        # Generate validation report
        report_generator = ReportGenerator(output_path)
        report = {
            "validation_type": "configuration",
            "customers_validated": len(customers_to_validate),
            "results": validation_results,
            "success": len(validation_results) == 0
        }
        
        report_generator.save_report(
            report, "configuration_validation",
            formats=["json", "md"]
        )
        
        # Summary
        if validation_results:
            click.echo(f"\n❌ Validation completed with {len(validation_results)} errors")
            click.echo(f"📋 Detailed report saved to {output_path}")
            sys.exit(ExitCode.VALIDATION_FAILED)
        else:
            click.echo(f"\n✅ All configurations validated successfully")
            sys.exit(ExitCode.SUCCESS)
            
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        click.echo(f"❌ Configuration validation failed: {e}")
        sys.exit(ExitCode.CONFIGURATION_ERROR)


@cli.command()
@click.option('--customer', '-c', help='Specific customer to validate (optional)')
@click.option('--environment', '-e', help='Specific environment to validate (optional)')
@click.option('--output-dir', default='validation-outputs', help='Directory for validation reports')
@click.pass_context
def artifacts(ctx, customer, environment, output_dir):
    """Validate artifact existence and content."""
    logger = get_logger(__name__)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        click.echo("🔍 Validating artifacts...")
        
        # Setup validation system
        orchestrator = setup_validation_system(
            ctx.obj['config_dir'],
            ctx.obj['terraform_dir'],
            ctx.obj['notebooks_dir']
        )
        
        validation_results = []
        customers_to_validate = []
        
        if customer:
            customers_to_validate.append(customer)
        else:
            customers_to_validate = orchestrator.config_loader.get_customer_list()
            click.echo(f"Validating artifacts for {len(customers_to_validate)} customers...")
        
        for customer_name in customers_to_validate:
            click.echo(f"\n📦 Validating artifacts for: {customer_name}")
            
            environments_to_check = [environment] if environment else ["dev", "test", "prod"]
            
            for env in environments_to_check:
                try:
                    # Check artifact existence
                    artifact_validation = orchestrator.artifact_manager.validate_artifacts_exist(customer_name, env)
                    
                    if artifact_validation.all_present:
                        click.echo(f"   ✅ All required artifacts present for '{env}'")
                        
                        # Validate artifact content
                        artifacts = orchestrator.artifact_manager.discover_customer_artifacts(customer_name, env)
                        content_validation = orchestrator.artifact_manager.validate_artifact_content(artifacts)
                        
                        if content_validation.is_valid:
                            click.echo(f"   ✅ All artifacts have valid content for '{env}'")
                        else:
                            click.echo(f"   ❌ Some artifacts have invalid content for '{env}'")
                            for invalid_notebook in content_validation.invalid_notebooks:
                                click.echo(f"      • {invalid_notebook}")
                            
                            validation_results.append({
                                "customer": customer_name,
                                "environment": env,
                                "type": "content_validation",
                                "status": "failed",
                                "invalid_artifacts": [str(nb) for nb in content_validation.invalid_notebooks]
                            })
                    else:
                        click.echo(f"   ❌ Missing artifacts for '{env}':")
                        for missing in artifact_validation.missing_artifacts:
                            click.echo(f"      • {missing}")
                        
                        validation_results.append({
                            "customer": customer_name,
                            "environment": env,
                            "type": "missing_artifacts",
                            "status": "failed",
                            "missing_artifacts": artifact_validation.missing_artifacts
                        })
                        
                except Exception as e:
                    click.echo(f"   ❌ Artifact validation failed for '{env}': {e}")
                    validation_results.append({
                        "customer": customer_name,
                        "environment": env,
                        "type": "validation_error",
                        "status": "failed",
                        "error": str(e)
                    })
        
        # Generate validation report
        report_generator = ReportGenerator(output_path)
        report = {
            "validation_type": "artifacts",
            "customers_validated": len(customers_to_validate),
            "results": validation_results,
            "success": len(validation_results) == 0
        }
        
        report_generator.save_report(
            report, "artifact_validation",
            formats=["json", "md"]
        )
        
        # Summary
        if validation_results:
            click.echo(f"\n❌ Artifact validation completed with {len(validation_results)} issues")
            click.echo(f"📋 Detailed report saved to {output_path}")
            sys.exit(ExitCode.ARTIFACT_ERROR)
        else:
            click.echo(f"\n✅ All artifacts validated successfully")
            sys.exit(ExitCode.SUCCESS)
            
    except Exception as e:
        logger.error(f"Artifact validation failed: {e}")
        click.echo(f"❌ Artifact validation failed: {e}")
        sys.exit(ExitCode.ARTIFACT_ERROR)


@cli.command()
@click.option('--customer', '-c', help='Specific customer to validate (optional)')
@click.option('--environment', '-e', help='Specific environment to validate (optional)')
@click.option('--output-dir', default='validation-outputs', help='Directory for validation reports')
@click.pass_context
def readiness(ctx, customer, environment, output_dir):
    """Validate deployment readiness."""
    logger = get_logger(__name__)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        click.echo("🔍 Validating deployment readiness...")
        
        # Setup validation system
        orchestrator = setup_validation_system(
            ctx.obj['config_dir'],
            ctx.obj['terraform_dir'],
            ctx.obj['notebooks_dir']
        )
        
        validation_results = []
        customers_to_validate = []
        
        if customer:
            customers_to_validate.append(customer)
        else:
            customers_to_validate = orchestrator.config_loader.get_customer_list()
            click.echo(f"Validating readiness for {len(customers_to_validate)} customers...")
        
        for customer_name in customers_to_validate:
            click.echo(f"\n🚀 Validating readiness for: {customer_name}")
            
            environments_to_check = [environment] if environment else ["dev", "test", "prod"]
            
            for env in environments_to_check:
                try:
                    # Comprehensive readiness validation
                    readiness_result = orchestrator.validate_deployment_readiness(customer_name, env)
                    
                    if readiness_result.success:
                        click.echo(f"   ✅ Ready for deployment to '{env}'")
                        if readiness_result.warnings:
                            click.echo(f"   ⚠️  Warnings for '{env}':")
                            for warning in readiness_result.warnings:
                                click.echo(f"      • {warning}")
                    else:
                        click.echo(f"   ❌ Not ready for deployment to '{env}':")
                        for error in readiness_result.errors:
                            click.echo(f"      • {error}")
                        
                        validation_results.append({
                            "customer": customer_name,
                            "environment": env,
                            "status": "not_ready",
                            "errors": readiness_result.errors,
                            "warnings": readiness_result.warnings,
                            "checks_performed": readiness_result.checks_performed
                        })
                        
                except Exception as e:
                    click.echo(f"   ❌ Readiness validation failed for '{env}': {e}")
                    validation_results.append({
                        "customer": customer_name,
                        "environment": env,
                        "status": "validation_error",
                        "error": str(e)
                    })
        
        # Generate validation report
        report_generator = ReportGenerator(output_path)
        report = {
            "validation_type": "deployment_readiness",
            "customers_validated": len(customers_to_validate),
            "results": validation_results,
            "success": len(validation_results) == 0
        }
        
        report_generator.save_report(
            report, "readiness_validation",
            formats=["json", "xml", "md"]
        )
        
        # Summary
        if validation_results:
            click.echo(f"\n❌ Readiness validation found {len(validation_results)} issues")
            click.echo(f"📋 Detailed report saved to {output_path}")
            sys.exit(ExitCode.VALIDATION_FAILED)
        else:
            click.echo(f"\n✅ All customers ready for deployment")
            sys.exit(ExitCode.SUCCESS)
            
    except Exception as e:
        logger.error(f"Readiness validation failed: {e}")
        click.echo(f"❌ Readiness validation failed: {e}")
        sys.exit(ExitCode.VALIDATION_FAILED)


@cli.command()
@click.option('--output-dir', default='validation-outputs', help='Directory for validation reports')
@click.pass_context
def terraform(ctx, output_dir):
    """Validate Terraform configuration."""
    logger = get_logger(__name__)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        click.echo("🔍 Validating Terraform configuration...")
        
        # Setup Terraform wrapper
        terraform_path = Path(ctx.obj['terraform_dir'])
        terraform_wrapper = TerraformWrapper(terraform_path)
        
        # Validate Terraform config
        validation_result = terraform_wrapper.validate_terraform_config()
        
        if validation_result.success:
            click.echo("✅ Terraform configuration is valid")
            if validation_result.warnings:
                click.echo("⚠️  Terraform warnings:")
                for warning in validation_result.warnings:
                    click.echo(f"   • {warning}")
        else:
            click.echo("❌ Terraform configuration validation failed:")
            for error in validation_result.errors:
                click.echo(f"   • {error}")
        
        # Generate validation report
        report_generator = ReportGenerator(output_path)
        terraform_report = report_generator.generate_validation_report(
            validation_result, "terraform_configuration"
        )
        
        report_generator.save_report(
            terraform_report, "terraform_validation",
            formats=["json", "xml", "md"]
        )
        
        if validation_result.success:
            sys.exit(ExitCode.SUCCESS)
        else:
            sys.exit(ExitCode.TERRAFORM_ERROR)
            
    except Exception as e:
        logger.error(f"Terraform validation failed: {e}")
        click.echo(f"❌ Terraform validation failed: {e}")
        sys.exit(ExitCode.TERRAFORM_ERROR)


@cli.command()
@click.option('--customer', '-c', help='Specific customer to validate (optional)')
@click.option('--environment', '-e', help='Specific environment to validate (optional)')
@click.option('--output-dir', default='validation-outputs', help='Directory for validation reports')
@click.pass_context
def all(ctx, customer, environment, output_dir):
    """Run all validation checks."""
    logger = get_logger(__name__)
    
    click.echo("🔍 Running comprehensive validation suite...")
    
    exit_codes = []
    
    # Run configuration validation
    try:
        ctx.invoke(config, customer=customer, environment=environment, output_dir=output_dir)
        exit_codes.append(ExitCode.SUCCESS)
    except SystemExit as e:
        exit_codes.append(e.code)
    
    # Run artifact validation
    try:
        ctx.invoke(artifacts, customer=customer, environment=environment, output_dir=output_dir)
        exit_codes.append(ExitCode.SUCCESS)
    except SystemExit as e:
        exit_codes.append(e.code)
    
    # Run readiness validation
    try:
        ctx.invoke(readiness, customer=customer, environment=environment, output_dir=output_dir)
        exit_codes.append(ExitCode.SUCCESS)
    except SystemExit as e:
        exit_codes.append(e.code)
    
    # Run Terraform validation
    try:
        ctx.invoke(terraform, output_dir=output_dir)
        exit_codes.append(ExitCode.SUCCESS)
    except SystemExit as e:
        exit_codes.append(e.code)
    
    # Summary
    success_count = sum(1 for code in exit_codes if code == ExitCode.SUCCESS)
    total_checks = len(exit_codes)
    
    click.echo(f"\n📊 Validation Summary:")
    click.echo(f"   • Total checks: {total_checks}")
    click.echo(f"   • Successful: {success_count}")
    click.echo(f"   • Failed: {total_checks - success_count}")
    
    if success_count == total_checks:
        click.echo("✅ All validation checks passed")
        sys.exit(ExitCode.SUCCESS)
    else:
        click.echo("❌ Some validation checks failed")
        # Return the first non-success exit code
        for code in exit_codes:
            if code != ExitCode.SUCCESS:
                sys.exit(code)


if __name__ == "__main__":
    cli()