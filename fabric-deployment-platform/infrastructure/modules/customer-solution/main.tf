# Customer Solution Module - Main Configuration (ALL SYNTAX ERRORS FIXED)
# Integrates with Fabric Deployment Platform ConfigLoader and TerraformWrapper
# Deploys Microsoft Fabric resources following medallion architecture

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
}

# Local values for resource naming and conditional logic
locals {
  # Workspace name with override support
  workspace_name = var.resource_name_overrides.workspace_name != "" ? var.resource_name_overrides.workspace_name : "${var.customer_prefix}-${var.environment}"
  
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
  
  # Generate lakehouse configurations with name overrides - FIXED SYNTAX
  lakehouses = {
    bronze = {
      name    = var.resource_name_overrides.bronze_lakehouse_name != "" ? var.resource_name_overrides.bronze_lakehouse_name : "${var.customer_prefix}-bronze-lh"
      enabled = var.bronze_layer
    }
    silver = {
      name    = var.resource_name_overrides.silver_lakehouse_name != "" ? var.resource_name_overrides.silver_lakehouse_name : "${var.customer_prefix}-silver-lh"
      enabled = var.silver_layer
    }
    gold = {
      name    = var.resource_name_overrides.gold_lakehouse_name != "" ? var.resource_name_overrides.gold_lakehouse_name : "${var.customer_prefix}-gold-lh"
      enabled = var.gold_layer
    }
  }
  
  # Pipeline name with override support - FIXED SYNTAX
  pipeline_name = var.resource_name_overrides.pipeline_name != "" ? var.resource_name_overrides.pipeline_name : "${var.customer_prefix}-orchestration-pipeline"
  
  # Common tags for all resources
  common_tags = merge(var.tags, {
    customer     = var.customer_name
    environment  = var.environment
    managed_by   = "terraform"
    architecture = "medallion"
  })
}

# Data source for capacity information (if needed)
data "fabric_capacity" "workspace_capacity" {
  count = var.fabric_capacity_id != null ? 1 : 0
  id    = var.fabric_capacity_id
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

# Workspace Capacity Assignment (CRITICAL FIX)
# Assign workspace to capacity for functionality
resource "fabric_workspace_capacity_assignment" "workspace_capacity" {
  count = var.fabric_capacity_id != null ? 1 : 0
  
  workspace_id = local.workspace_id
  capacity_id  = var.fabric_capacity_id
  
  # Ensure workspace exists before assignment
  depends_on = [fabric_workspace.customer_workspace]
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
  
  # Ensure workspace and capacity assignment exist
  depends_on = [
    fabric_workspace.customer_workspace,
    fabric_workspace_capacity_assignment.workspace_capacity
  ]
}

# Notebook Resources - Deploy from generated .ipynb files
resource "fabric_notebook" "layer_notebooks" {
  for_each = var.notebook_files
  
  workspace_id = local.workspace_id
  display_name = each.key
  description  = "Generated notebook for ${var.customer_name} - ${each.key}"
  format       = "ipynb"
  
  # IMPROVEMENT: Explicitly set definition_update_enabled
  definition_update_enabled = var.debug_mode ? true : false
  
  # Use definition with source file path
  definition = {
    "notebook-content.ipynb" = {
      source = each.value
      # Add tokens support for template variables
      tokens = {
        "customer_name"   = var.customer_name
        "customer_prefix" = var.customer_prefix
        "environment"     = var.environment
      }
    }
  }
  
  # Ensure lakehouses exist before creating notebooks
  depends_on = [fabric_lakehouse.layer_lakehouses]
}

# CRITICAL FIX: Create pipeline template file resource
# This creates the pipeline definition that was missing
resource "local_file" "pipeline_template" {
  count = length(var.notebook_files) > 0 ? 1 : 0
  
  filename = "${path.module}/generated-pipeline-content.json"
  content = jsonencode({
    "$schema" = "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#"
    "contentVersion" = "1.0.0.0"
    "parameters" = {}
    "variables" = {
      "customerPrefix" = var.customer_prefix
      "environment"    = var.environment
    }
    "resources" = []
    "outputs" = {}
    "activities" = [
      {
        "name" = "ExecuteNotebooks"
        "type" = "ForEach"
        "typeProperties" = {
          "items" = {
            "value" = "@pipeline().parameters.notebooks"
            "type"  = "Expression"
          }
          "activities" = [
            {
              "name" = "RunNotebook"
              "type" = "Notebook"
              "typeProperties" = {
                "notebook" = {
                  "referenceName" = "@item().name"
                  "type" = "NotebookReference"
                }
              }
            }
          ]
        }
      }
    ]
  })
}

# Data Pipeline Resources for orchestration
resource "fabric_data_pipeline" "orchestration_pipeline" {
  count = length(var.notebook_files) > 0 ? 1 : 0
  
  workspace_id = local.workspace_id
  display_name = local.pipeline_name
  description  = "Main orchestration pipeline for ${var.customer_name}"
  format       = "Default"
  
  # IMPROVEMENT: Explicitly set definition_update_enabled
  definition_update_enabled = var.debug_mode ? true : false
  
  # Use the generated pipeline definition file
  definition = {
    "pipeline-content.json" = {
      source = local_file.pipeline_template[0].filename
      tokens = {
        "customer_prefix" = var.customer_prefix
        "environment"     = var.environment
        "workspace_id"    = local.workspace_id
      }
    }
  }
  
  # Ensure notebooks and template exist before creating pipeline
  depends_on = [
    fabric_notebook.layer_notebooks,
    local_file.pipeline_template
  ]
}