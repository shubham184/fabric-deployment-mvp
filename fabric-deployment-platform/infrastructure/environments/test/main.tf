# Test Environment - Main Configuration
# Integrates with existing TerraformWrapper and ConfigLoader

terraform {
  required_version = ">= 1.8, < 2.0"
  
  required_providers {
    fabric = {
      source  = "microsoft/fabric"
      version = "1.3.0"
    }
  }
  
  # Backend configuration for state management
  # Configure this based on your existing state management strategy
  backend "azurerm" {
    # resource_group_name  = "terraform-state-rg"
    # storage_account_name = "terraformstate"
    # container_name       = "tfstate"
    # key                 = "fabric-test.tfstate"
    
    # Alternatively, configure these via backend config file or environment variables
    # See: https://developer.hashicorp.com/terraform/language/settings/backends/azurerm
  }
}

# Provider configuration for Microsoft Fabric
# Authentication should be configured via environment variables or Azure CLI
provider "fabric" {
  # Authentication will be handled by the environment or service principal
  # No explicit configuration needed if using Azure CLI or environment variables
  
  # For service principal authentication, use environment variables:
  # FABRIC_CLIENT_ID
  # FABRIC_CLIENT_SECRET  
  # FABRIC_TENANT_ID
  
  # For user authentication (development), ensure Azure CLI is logged in
  # az login --scope https://analysis.windows.net/powerbi/api/.default
}

# Local values for environment-specific configuration
locals {
  environment = "test"
  
  # Default notebook files mapping - can be overridden by variables
  default_notebook_files = {
    for file_path in fileset("${path.root}/generated-notebooks/${var.customer_prefix}/${local.environment}", "*.ipynb") :
    trimsuffix(basename(file_path), ".ipynb") => "${path.root}/generated-notebooks/${var.customer_prefix}/${local.environment}/${file_path}"
  }
  
  # Merge provided notebook files with discovered files
  notebook_files = merge(local.default_notebook_files, var.notebook_files_override)
  
  # Environment-specific tags
  environment_tags = merge(var.tags, {
    environment = local.environment
    deployed_by = "terraform"
    module_version = "1.0.0"
  })
}

# Customer Solution Module instantiation
module "customer_solution" {
  source = "../../modules/customer-solution"
  
  # Customer Information (from TerraformWrapper)
  customer_name   = var.customer_name
  customer_prefix = var.customer_prefix
  environment     = local.environment
  
  # Workspace Configuration
  workspace_id      = var.workspace_id
  fabric_capacity_id = var.fabric_capacity_id
  
  # Medallion Architecture Configuration
  bronze_layer = var.bronze_layer
  silver_layer = var.silver_layer
  gold_layer   = var.gold_layer
  
  # Notebook Files
  notebook_files = local.notebook_files
  
  # Resource Configuration
  tags       = local.environment_tags
  debug_mode = var.debug_mode
  
  # Advanced Configuration
  pipeline_schedule = var.pipeline_schedule
  lakehouse_settings = var.lakehouse_settings
  workspace_settings = var.workspace_settings
  
  # Resource Naming Overrides
  resource_name_overrides = var.resource_name_overrides
}

# Output workspace information for platform integration
output "workspace_info" {
  description = "Workspace information for platform integration"
  value = {
    workspace_id   = module.customer_solution.workspace_id
    workspace_name = module.customer_solution.workspace_name
    workspace_url  = module.customer_solution.workspace_url
    environment    = local.environment
  }
}

# Output deployment summary for testing validation
output "deployment_summary" {
  description = "Summary of deployed resources for testing"
  value       = module.customer_solution.deployment_summary
}