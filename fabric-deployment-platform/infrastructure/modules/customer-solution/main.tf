# Customer Solution Module - Main Configuration (SIMPLIFIED APPROACH)
# Deploys PREDEFINED artifacts (pipelines & notebooks) to Microsoft Fabric
# Terraform = Deployment Tool, NOT Content Creator

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
  
  # Generate lakehouse configurations with name overrides
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
  
  # Pipeline name with override support
  pipeline_name = var.resource_name_overrides.pipeline_name != "" ? var.resource_name_overrides.pipeline_name : "${var.customer_prefix}-pipeline"
  
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

# Workspace Capacity Assignment (REQUIRED FOR FUNCTIONALITY)
# Assign workspace to capacity for compute resources
resource "fabric_workspace_capacity_assignment" "workspace_capacity" {
  count = var.fabric_capacity_id != null ? 1 : 0
  
  workspace_id = local.workspace_id
  capacity_id  = var.fabric_capacity_id
  
  # Ensure workspace exists before assignment
  depends_on = [fabric_workspace.customer_workspace]
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

# Notebook Resources - Deploy PREDEFINED .ipynb files
resource "fabric_notebook" "predefined_notebooks" {
  for_each = var.predefined_notebooks
  
  workspace_id = local.workspace_id
  display_name = "${var.customer_prefix}-${each.key}"
  description  = "Notebook: ${each.key} for ${var.customer_name}"
  format       = "ipynb"
  
  # Control whether notebooks update when source changes
  definition_update_enabled = var.notebook_update_enabled
  
  # Deploy predefined notebook with customer-specific tokens
  definition = {
    "notebook-content.ipynb" = {
      source = each.value.source_path
      tokens = merge({
        # Standard tokens for all notebooks
        "customer_name"   = var.customer_name
        "customer_prefix" = var.customer_prefix
        "environment"     = var.environment
        "workspace_id"    = local.workspace_id
        # Layer-specific lakehouse IDs (if lakehouses exist)
        "bronze_lakehouse_id" = var.bronze_layer && contains(keys(fabric_lakehouse.layer_lakehouses), "bronze") ? fabric_lakehouse.layer_lakehouses["bronze"].id : ""
        "silver_lakehouse_id" = var.silver_layer && contains(keys(fabric_lakehouse.layer_lakehouses), "silver") ? fabric_lakehouse.layer_lakehouses["silver"].id : ""
        "gold_lakehouse_id"   = var.gold_layer && contains(keys(fabric_lakehouse.layer_lakehouses), "gold") ? fabric_lakehouse.layer_lakehouses["gold"].id : ""
      }, each.value.custom_tokens)
    }
  }
  
  # Ensure lakehouses exist before creating notebooks
  depends_on = [fabric_lakehouse.layer_lakehouses]
}

# Data Pipeline Resource - Deploy PREDEFINED pipeline
resource "fabric_data_pipeline" "predefined_pipeline" {
  count = var.predefined_pipeline.enabled ? 1 : 0
  
  workspace_id = local.workspace_id
  display_name = local.pipeline_name
  description  = "Pipeline: ${var.predefined_pipeline.pipeline_type} for ${var.customer_name}"
  format       = "Default"
  
  # Control whether pipeline updates when source changes
  definition_update_enabled = var.pipeline_update_enabled
  
  # Deploy predefined pipeline with customer-specific tokens
  definition = {
    "pipeline-content.json" = {
      source = var.predefined_pipeline.source_path
      tokens = merge({
        # Standard tokens for pipeline
        "customer_name"   = var.customer_name
        "customer_prefix" = var.customer_prefix
        "environment"     = var.environment
        "workspace_id"    = local.workspace_id
        # Notebook references
        "notebooks" = jsonencode([
          for notebook_key, notebook_config in var.predefined_notebooks : {
            name = "${var.customer_prefix}-${notebook_key}"
            id   = fabric_notebook.predefined_notebooks[notebook_key].id
          }
        ])
        # Lakehouse references
        "bronze_lakehouse_name" = var.bronze_layer && contains(keys(fabric_lakehouse.layer_lakehouses), "bronze") ? fabric_lakehouse.layer_lakehouses["bronze"].display_name : ""
        "silver_lakehouse_name" = var.silver_layer && contains(keys(fabric_lakehouse.layer_lakehouses), "silver") ? fabric_lakehouse.layer_lakehouses["silver"].display_name : ""
        "gold_lakehouse_name"   = var.gold_layer && contains(keys(fabric_lakehouse.layer_lakehouses), "gold") ? fabric_lakehouse.layer_lakehouses["gold"].display_name : ""
      }, var.predefined_pipeline.custom_tokens)
    }
  }
  
  # Ensure notebooks exist before creating pipeline
  depends_on = [fabric_notebook.predefined_notebooks]
}