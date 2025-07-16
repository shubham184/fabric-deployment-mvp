#!/usr/bin/env python3
"""
Simplified deployment script for Fabric platform MVP with enhanced validation.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import yaml

# Suppress Azure SDK verbose logging
import logging as _logging
_logging.getLogger("azure").setLevel(_logging.WARNING)
_logging.getLogger("urllib3").setLevel(_logging.WARNING)

# Import validator only if running from scripts directory
try:
    from validate import FabricValidator
except ImportError:
    # If imported as a module, use absolute import
    from scripts.validate import FabricValidator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


class FabricDeployer:
    """Simple deployer that validates thoroughly before running Terraform."""
    
    def __init__(self, customer_name: str, environment: str = "dev"):
        self.customer_name = customer_name
        self.environment = environment
        self.project_root = Path(__file__).parent.parent
        self.terraform_dir = self.project_root / "terraform"
        self.validator = FabricValidator(self.project_root)
        
    def load_config(self) -> dict:
        """Load customer configuration file."""
        config_path = self.project_root / "configs" / "customers" / f"{self.customer_name}.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Customer config not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        return config
    
    def prepare_terraform_vars(self, config: dict) -> dict:
        """Prepare variables for Terraform."""
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
        
        # Merge environment-specific settings
        tf_vars.update(env_config)
        
        return tf_vars
    
    def run_terraform(self, tf_vars: dict) -> bool:
        """Run Terraform deployment."""
        os.chdir(self.terraform_dir)
        
        # Write variables to tfvars file
        tfvars_path = self.terraform_dir / f"{self.customer_name}-{self.environment}.auto.tfvars.json"
        with open(tfvars_path, 'w') as f:
            json.dump(tf_vars, f, indent=2)
        
        logger.info(f"Wrote Terraform variables to {tfvars_path}")
        
        # Check if secrets.tfvars exists
        secrets_file = self.terraform_dir / "secrets.tfvars"
        var_file_args = []
        if secrets_file.exists():
            logger.info(f"Found secrets file: {secrets_file}")
            var_file_args = ["-var-file=secrets.tfvars"]
        else:
            print("⚠️  No secrets.tfvars file found. Make sure authentication is configured via environment variables.")
        
        try:
            # Initialize Terraform
            logger.info("Running terraform init...")
            result = subprocess.run(
                ["terraform", "init"],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Terraform init failed: {result.stderr}")
                return False
            
            # Plan deployment
            logger.info("Running terraform plan...")
            plan_cmd = ["terraform", "plan", "-out=tfplan"] + var_file_args
            result = subprocess.run(
                plan_cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Terraform plan failed: {result.stderr}")
                return False
            
            # Show plan summary
            logger.info(result.stdout)
            
            # Check if auto-approve is set
            auto_approve = os.environ.get("TF_CLI_ARGS_apply") == "-auto-approve"
            
            if not auto_approve:
                # Apply deployment with confirmation
                response = input("\nProceed with deployment? (yes/no): ")
                if response.lower() != "yes":
                    print("Deployment cancelled")
                    return False
            
            logger.info("Running terraform apply...")
            apply_cmd = ["terraform", "apply", "tfplan"]
            result = subprocess.run(
                apply_cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Terraform apply failed: {result.stderr}")
                return False
            
            print("✓ Deployment completed successfully!")
            
            # Get and display outputs
            print("\nRetrieving deployment outputs...")
            output_result = subprocess.run(
                ["terraform", "output", "-json"],
                capture_output=True,
                text=True
            )
            
            if output_result.returncode == 0:
                try:
                    outputs = json.loads(output_result.stdout)
                    if outputs and "deployment_summary" in outputs:
                        summary = outputs["deployment_summary"]["value"]
                        print("\n📊 Deployment Summary:")
                        print(f"  Customer: {summary.get('customer')}")
                        print(f"  Environment: {summary.get('environment')}")
                        print(f"  Workspace ID: {summary.get('workspace_id')}")
                        print(f"  Lakehouses: {summary.get('lakehouses_created')}")
                        print(f"  Notebooks: {summary.get('notebooks_deployed')}")
                        print(f"  Pipelines: {summary.get('pipelines_deployed')}")
                except json.JSONDecodeError:
                    pass
            
            return True
            
        except Exception as e:
            logger.error(f"Terraform execution failed: {e}")
            return False
    
    def deploy(self) -> bool:
        """Main deployment method with enhanced validation."""
        print(f"\n🚀 Starting deployment for {self.customer_name} ({self.environment})")
        
        try:
            # Run comprehensive validation
            print("\n🔍 Running pre-flight validation checks...")
            success, errors, warnings = self.validator.validate_all(self.customer_name, self.environment)
            
            # Display validation results
            if warnings:
                print("\n⚠️  Validation Warnings:")
                for warning in warnings:
                    print(f"   • {warning}")
                    
            if errors:
                print("\n❌ Validation Errors:")
                for error in errors:
                    print(f"   • {error}")
                print(f"\nValidation failed with {len(errors)} error(s)")
                print("Please fix the above errors before proceeding.")
                return False
                
            print("\n✅ All validation checks passed!")
            
            # Load configuration
            config = self.load_config()
            
            # Prepare Terraform variables
            tf_vars = self.prepare_terraform_vars(config)
            
            # Run Terraform
            print("\n🔧 Proceeding with Terraform deployment...")
            return self.run_terraform(tf_vars)
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Deploy Fabric artifacts for a customer")
    parser.add_argument("customer", help="Customer name (e.g., contoso)")
    parser.add_argument("--environment", "-e", default="dev", choices=["dev", "prod", "test", "staging"],
                       help="Deployment environment (default: dev)")
    parser.add_argument("--auto-approve", action="store_true",
                       help="Skip confirmation prompt")
    parser.add_argument("--skip-validation", action="store_true",
                       help="Skip validation checks (not recommended)")
    
    args = parser.parse_args()
    
    # Override confirmation for auto-approve
    if args.auto_approve:
        os.environ["TF_CLI_ARGS_apply"] = "-auto-approve"
        print("✓ Auto-approve mode enabled")
    
    if args.skip_validation:
        print("⚠️  Validation checks skipped - this is not recommended!")
    
    deployer = FabricDeployer(args.customer, args.environment)
    
    if deployer.deploy():
        print("\n🎉 Deployment successful!")
        sys.exit(0)
    else:
        print("\n❌ Deployment failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()