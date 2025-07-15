# Development Environment - Main Configuration (SYNTAX FIXED)
# Integrates with existing TerraformWrapper and ConfigLoader

terraform {
  required_version = ">= 1.8, < 2.0"
  
  required_providers {
    fabric = {
      source  = "microsoft/fabric"
      version = "1.3.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }
  
  # Backend configuration for state management
  backend "azurerm" {
    # Configure these via backend config file or environment variables
    # Example backend.hcl file:
    # resource_group_name  = "terraform-state-rg"
    # storage_account_name = "terraformstate12345"
    # container_name       = "tfstate"
    # key                 = "fabric-dev.tfstate"
  }
}

# Enhanced Provider configuration for Microsoft Fabric
provider "fabric" {
  # For development: Azure CLI authentication is acceptable
  # For production: Always use Service Principal
  
  # Enable preview features for development environment
  preview = var.enable_preview_features
  
  # Optional: Explicitly configure authentication method for development
  use_cli = true
  use_msi = false
  use_oidc = false
}

# Local values for environment-specific configuration
locals {
  environment = "dev"
  
  # Improved notebook file discovery with validation
  discovered_notebook_files = var.validate_notebook_files ? {
    for file_path in fileset("${path.root}/generated-notebooks/${var.customer_prefix}/${local.environment}", "*.ipynb") :
    trimsuffix(basename(file_path), ".ipynb") => "${path.root}/generated-notebooks/${var.customer_prefix}/${local.environment}/${file_path}"
    if fileexists("${path.root}/generated-notebooks/${var.customer_prefix}/${local.environment}/${file_path}")
  } : {}
  
  # Merge provided notebook files with discovered files
  notebook_files = merge(local.discovered_notebook_files, var.notebook_files_override)
  
  # Environment-specific tags with additional development metadata
  environment_tags = merge(var.tags, {
    environment = local.environment
    deployed_by = "terraform"
    module_version = "1.0.0"
    deployment_time = timestamp()
    debug_mode = var.debug_mode
  })
  
  # Validate required capacity for development
  capacity_required = var.fabric_capacity_id != null && var.fabric_capacity_id != ""
}

# Customer Solution Module instantiation with enhanced configuration
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
  
  # Notebook Files (validated)
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

# Enhanced outputs for development environment
output "workspace_info" {
  description = "Workspace information for platform integration"
  value = {
    workspace_id   = module.customer_solution.workspace_id
    workspace_name = module.customer_solution.workspace_name
    workspace_url  = module.customer_solution.workspace_url
    environment    = local.environment
    capacity_assigned = var.fabric_capacity_id != null
    debug_mode = var.debug_mode
  }
}

output "deployment_summary" {
  description = "Enhanced deployment summary for development"
  value = merge(module.customer_solution.deployment_summary, {
    validation_status = {
      notebook_files_found = length(local.notebook_files)
      capacity_configured = local.capacity_required
    }
    development_info = {
      preview_features_enabled = var.enable_preview_features
      auto_cleanup_enabled = var.auto_cleanup_after_tests
      integration_tests = var.run_integration_tests
    }
  })
}

# Development-specific outputs
output "development_endpoints" {
  description = "Development-specific endpoints and information"
  value = {
    workspace_portal_url = "https://app.fabric.microsoft.com/groups/${module.customer_solution.workspace_id}"
    lakehouse_urls = module.customer_solution.resource_urls.lakehouses
    notebook_urls = module.customer_solution.resource_urls.notebooks
    pipeline_url = module.customer_solution.resource_urls.pipeline
  }
}

output "quick_access_commands" {
  description = "Quick access commands for development"
  value = {
    terraform_destroy = "terraform destroy -var-file=\"terraform.tfvars\""
    workspace_access = "az login --scope https://analysis.windows.net/powerbi/api/.default"
    debug_info = var.debug_mode ? {
      workspace_id = module.customer_solution.workspace_id
      resource_count = module.customer_solution.deployment_summary.resource_counts
    } : "Enable debug_mode for detailed information"
  }
}