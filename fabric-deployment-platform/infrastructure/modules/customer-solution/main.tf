# Customer Solution Module - Main Configuration
# Integrates with Fabric Deployment Platform ConfigLoader and TerraformWrapper
# Deploys Microsoft Fabric resources following medallion architecture

terraform {
  required_version = ">= 1.8, < 2.0"
  required_providers {
    fabric = {
      source  = "microsoft/fabric"
      version = "1.3.0"
    }
  }
}

# Local values for resource naming and conditional logic
locals {
  workspace_name = "${var.customer_prefix}-${var.environment}"
  
  # Determine if we should create a new workspace
  create_workspace = var.workspace_id == null || var.workspace_id == ""
  
  # Use provided workspace_id or reference the created workspace
  workspace_id = local.create_workspace ? fabric_workspace.customer_workspace[0].id : var.workspace_id
  
  # Define enabled layers for conditional resource creation
  enabled_layers = {
    bronze = var.bronze_layer
    silver = var.silver_layer
    gold   = var.gold_layer
  }
  
  # Generate lakehouse configurations
  lakehouses = {
    for layer in ["bronze", "silver", "gold"] :
    layer => {
      name    = "${var.customer_prefix}-${layer}-lh"
      enabled = local.enabled_layers[layer]
    }
  }
  
  # Common tags for all resources
  common_tags = merge(var.tags, {
    customer     = var.customer_name
    environment  = var.environment
    managed_by   = "terraform"
    architecture = "medallion"
  })
}

# Conditional Workspace Creation
# Only create if workspace_id is not provided
resource "fabric_workspace" "customer_workspace" {
  count = local.create_workspace ? 1 : 0
  
  display_name = local.workspace_name
  description  = "Workspace for ${var.customer_name} - ${var.environment} environment"
  
  lifecycle {
    create_before_destroy = true
  }
}

# Data source to reference existing workspace if provided
data "fabric_workspace" "existing_workspace" {
  count = local.create_workspace ? 0 : 1
  id    = var.workspace_id
}

# Lakehouse Resources - Conditional creation based on enabled layers
resource "fabric_lakehouse" "layer_lakehouses" {
  for_each = {
    for layer, config in local.lakehouses :
    layer => config if config.enabled
  }
  
  workspace_id = local.workspace_id
  display_name = each.value.name
  description  = "${title(each.key)} layer lakehouse for ${var.customer_name}"
  
  # Configure lakehouse with schemas enabled if specified
  configuration = {
    enable_schemas = var.lakehouse_settings.enable_schemas
  }
  
  # Ensure workspace exists before creating lakehouses
  depends_on = [fabric_workspace.customer_workspace]
}

# Notebook Resources - Deploy from generated .ipynb files
resource "fabric_notebook" "layer_notebooks" {
  for_each = var.notebook_files
  
  workspace_id = local.workspace_id
  display_name = each.key
  description  = "Generated notebook for ${var.customer_name} - ${each.key}"
  format       = "ipynb"
  
  # Use definition with source file path
  definition = {
    "notebook-content.ipynb" = {
      source = each.value
    }
  }
  
  # Ensure lakehouses exist before creating notebooks
  depends_on = [fabric_lakehouse.layer_lakehouses]
}

# Data Pipeline Resources for orchestration
resource "fabric_data_pipeline" "orchestration_pipeline" {
  count = length(var.notebook_files) > 0 ? 1 : 0
  
  workspace_id = local.workspace_id
  display_name = "${var.customer_prefix}-orchestration-pipeline"
  description  = "Main orchestration pipeline for ${var.customer_name}"
  format       = "Default"
  
  # Create a temporary pipeline definition file
  definition = {
    "pipeline-content.json" = {
      source = "${path.module}/pipeline-template.json"
      tokens = {
        "customer_prefix" = var.customer_prefix
        "environment"     = var.environment
      }
    }
  }
  
  # Ensure notebooks exist before creating pipeline
  depends_on = [fabric_notebook.layer_notebooks]
}