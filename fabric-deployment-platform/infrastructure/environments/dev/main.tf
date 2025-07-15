# Development Environment - Using Simplified Approach
# Shows how to deploy PREDEFINED artifacts to Microsoft Fabric

terraform {
  required_version = ">= 1.8, < 2.0"
  
  required_providers {
    fabric = {
      source  = "microsoft/fabric"
      version = "1.3.0"
    }
  }
}


# Provider configuration for Microsoft Fabric
provider "fabric" {
  # For development: Azure CLI authentication is acceptable
  use_cli = true
  preview = var.enable_preview_features
}

# Local values for environment-specific configuration
locals {
  environment = "dev"
  
  # Path to predefined artifacts (created by your platform's business/data teams)
  artifacts_base_path = "${path.root}/../../../predefined-artifacts"
  
  # Environment-specific tags
  environment_tags = merge(var.tags, {
    environment = local.environment
    deployed_by = "terraform"
    module_version = "1.0.0"
    deployment_time = timestamp()
  })
}

# Customer Solution Module instantiation with PREDEFINED artifacts
module "customer_solution" {
  source = "../../modules/customer-solution"
  
  # Customer Information
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
  
  # PREDEFINED NOTEBOOKS - Point to actual .ipynb files created by data team
  predefined_notebooks = {
    bronze-ingestion = {
      source_path = "${local.artifacts_base_path}/notebooks/bronze-ingestion.ipynb"
      custom_tokens = {
        "data_source_connection" = var.bronze_data_source
        "ingestion_frequency"    = "daily"
      }
    }
    silver-transformation = {
      source_path = "${local.artifacts_base_path}/notebooks/silver-transformation.ipynb"
      custom_tokens = {
        "transformation_rules" = var.transformation_config
        "quality_checks"       = "enabled"
      }
    }
    gold-analytics = {
      source_path = "${local.artifacts_base_path}/notebooks/gold-analytics.ipynb"
      custom_tokens = {
        "report_schedule" = "weekly"
        "dashboard_url"   = var.dashboard_endpoint
      }
    }
  }
  
  # PREDEFINED PIPELINE - Point to actual pipeline JSON created by business team
  predefined_pipeline = {
    enabled       = true
    pipeline_type = "medallion-basic"
    source_path   = "${local.artifacts_base_path}/pipelines/medallion-basic-pipeline.json"
    custom_tokens = {
      "schedule_frequency" = "0 2 * * *"  # Daily at 2 AM
      "error_email"        = var.admin_email
      "retry_attempts"     = "3"
    }
  }
  
  # Update Control (for development environment)
  notebook_update_enabled = true   # Auto-update when notebook files change
  pipeline_update_enabled = true   # Auto-update when pipeline file changes
  
  # Resource Configuration
  tags = local.environment_tags
  
  # Advanced Configuration
  lakehouse_settings = var.lakehouse_settings
  workspace_settings = var.workspace_settings
  
  # Resource Naming Overrides
  resource_name_overrides = var.resource_name_overrides
}

# Outputs for platform integration
output "workspace_info" {
  description = "Workspace information for platform integration"
  value = {
    workspace_id   = module.customer_solution.workspace_id
    workspace_name = module.customer_solution.workspace_name
    workspace_url  = module.customer_solution.workspace_url
    environment    = local.environment
  }
}

output "deployment_summary" {
  description = "Summary of deployed predefined artifacts"
  value = module.customer_solution.deployment_summary
}

output "predefined_artifacts_deployed" {
  description = "Details of predefined artifacts deployed"
  value = module.customer_solution.predefined_artifacts_summary
}

output "quick_access_urls" {
  description = "Direct URLs to deployed resources"
  value = module.customer_solution.resource_urls
}