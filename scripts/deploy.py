#!/usr/bin/env python3
"""
Simplified deployment script for Fabric platform MVP.
Reads customer config and runs Terraform.
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FabricDeployer:
    """Simple deployer that reads config and runs Terraform."""
    
    def __init__(self, customer_name: str, environment: str = "dev"):
        self.customer_name = customer_name
        self.environment = environment
        self.project_root = Path(__file__).parent.parent
        self.terraform_dir = self.project_root / "terraform"
        
    def load_config(self) -> dict:
        """Load customer configuration file."""
        config_path = self.project_root / "configs" / "customers" / f"{self.customer_name}.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Customer config not found: {config_path}")
        
        logger.info(f"Loading config from {config_path}")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        return config
    
    def validate_workspace_exists(self, workspace_id: str) -> bool:
        """Quick check if workspace ID is valid format."""
        # Basic GUID format validation
        guid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        if not re.match(guid_pattern, workspace_id):
            logger.error(f"Invalid workspace ID format: {workspace_id}")
            logger.error("Workspace ID must be a valid GUID (e.g., 00000000-0000-0000-0000-000000000000)")
            return False
        
        logger.info(f"✓ Workspace ID format is valid")
        return True
    
    def validate_artifacts(self, config: dict) -> bool:
        """Validate that all referenced artifacts exist."""
        all_valid = True
        
        # Check notebooks
        for name, notebook in config.get("artifacts", {}).get("notebooks", {}).items():
            path = self.project_root / notebook["path"]
            if not path.exists():
                logger.error(f"Notebook not found: {path}")
                all_valid = False
            else:
                logger.info(f"✓ Found notebook: {name}")
        
        # Check pipelines
        for name, pipeline in config.get("artifacts", {}).get("pipelines", {}).items():
            path = self.project_root / pipeline["path"]
            if not path.exists():
                logger.error(f"Pipeline not found: {path}")
                all_valid = False
            else:
                logger.info(f"✓ Found pipeline: {name}")
                
        return all_valid
    
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
            logger.warning("No secrets.tfvars file found. Make sure authentication is configured via environment variables.")
        
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
                logger.error("Common causes:")
                logger.error("  1. Invalid Service Principal credentials in secrets.tfvars")
                logger.error("  2. Service Principal doesn't have access to workspace")
                logger.error("  3. Network connectivity issues")
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
                logger.error("Common causes:")
                logger.error("  1. Workspace ID doesn't exist or Service Principal lacks access")
                logger.error("  2. Invalid artifact paths in customer config")
                logger.error("  3. Workspace not assigned to a Fabric capacity")
                return False
            
            # Show plan summary
            logger.info(result.stdout)
            
            # Check if auto-approve is set
            auto_approve = os.environ.get("TF_CLI_ARGS_apply") == "-auto-approve"
            
            if not auto_approve:
                # Apply deployment with confirmation
                response = input("\nProceed with deployment? (yes/no): ")
                if response.lower() != "yes":
                    logger.info("Deployment cancelled")
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
            
            logger.info("✓ Deployment completed successfully!")
            
            # Get and display outputs
            logger.info("\nRetrieving deployment outputs...")
            output_result = subprocess.run(
                ["terraform", "output", "-json"],
                capture_output=True,
                text=True
            )
            
            if output_result.returncode == 0:
                try:
                    outputs = json.loads(output_result.stdout)
                    if outputs:
                        logger.info("\n📊 Deployment Summary:")
                        if "deployment_summary" in outputs:
                            summary = outputs["deployment_summary"]["value"]
                            logger.info(f"  Customer: {summary.get('customer')}")
                            logger.info(f"  Environment: {summary.get('environment')}")
                            logger.info(f"  Workspace ID: {summary.get('workspace_id')}")
                            logger.info(f"  Lakehouses: {summary.get('lakehouses_created')}")
                            logger.info(f"  Notebooks: {summary.get('notebooks_deployed')}")
                            logger.info(f"  Pipelines: {summary.get('pipelines_deployed')}")
                except json.JSONDecodeError:
                    pass
            
            return True
            
        except Exception as e:
            logger.error(f"Terraform execution failed: {e}")
            return False
    
    def deploy(self) -> bool:
        """Main deployment method."""
        logger.info(f"Starting deployment for {self.customer_name} ({self.environment})")
        
        try:
            # Load configuration
            config = self.load_config()
            
            # Validate workspace ID format
            workspace_id = config["infrastructure"]["workspace_id"]
            if not self.validate_workspace_exists(workspace_id):
                return False
            
            # Validate artifacts exist
            if not self.validate_artifacts(config):
                logger.error("Artifact validation failed")
                return False
            
            # Prepare Terraform variables
            tf_vars = self.prepare_terraform_vars(config)
            
            # Run Terraform
            return self.run_terraform(tf_vars)
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Deploy Fabric artifacts for a customer")
    parser.add_argument("customer", help="Customer name (e.g., contoso)")
    parser.add_argument("--environment", "-e", default="dev", choices=["dev", "prod"],
                       help="Deployment environment (default: dev)")
    parser.add_argument("--auto-approve", action="store_true",
                       help="Skip confirmation prompt")
    
    args = parser.parse_args()
    
    # Override confirmation for auto-approve
    if args.auto_approve:
        os.environ["TF_CLI_ARGS_apply"] = "-auto-approve"
        logger.info("Auto-approve mode enabled")
    
    deployer = FabricDeployer(args.customer, args.environment)
    
    if deployer.deploy():
        logger.info("🎉 Deployment successful!")
        sys.exit(0)
    else:
        logger.error("❌ Deployment failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()