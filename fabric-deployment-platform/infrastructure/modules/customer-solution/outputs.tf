# Customer Solution Module - Output Definitions (SIMPLIFIED APPROACH)
# Outputs for integration with existing platform and verification

# Workspace Outputs
output "workspace_id" {
  description = "ID of the Fabric workspace (created or existing)"
  value       = local.workspace_id
}

output "workspace_name" {
  description = "Name of the Fabric workspace"
  value       = local.workspace_name
}

output "workspace_url" {
  description = "URL to access the Fabric workspace"
  value       = "https://app.fabric.microsoft.com/groups/${local.workspace_id}"
}

output "workspace_created" {
  description = "Whether a new workspace was created by this module"
  value       = local.create_workspace
}

# Lakehouse Outputs
output "lakehouses" {
  description = "Map of created lakehouses with their details"
  value = {
    for layer, lakehouse in fabric_lakehouse.layer_lakehouses : layer => {
      id           = lakehouse.id
      name         = lakehouse.display_name
      workspace_id = lakehouse.workspace_id
      url          = "https://app.fabric.microsoft.com/groups/${lakehouse.workspace_id}/lakehouses/${lakehouse.id}"
      layer        = layer
    }
  }
}

output "lakehouse_ids" {
  description = "Map of lakehouse layer names to their IDs"
  value = {
    for layer, lakehouse in fabric_lakehouse.layer_lakehouses : layer => lakehouse.id
  }
}

output "lakehouse_names" {
  description = "Map of lakehouse layer names to their display names"
  value = {
    for layer, lakehouse in fabric_lakehouse.layer_lakehouses : layer => lakehouse.display_name
  }
}

# Specific layer outputs for easier access
output "bronze_lakehouse_id" {
  description = "ID of the bronze lakehouse (if enabled)"
  value       = var.bronze_layer && contains(keys(fabric_lakehouse.layer_lakehouses), "bronze") ? fabric_lakehouse.layer_lakehouses["bronze"].id : null
}

output "silver_lakehouse_id" {
  description = "ID of the silver lakehouse (if enabled)"
  value       = var.silver_layer && contains(keys(fabric_lakehouse.layer_lakehouses), "silver") ? fabric_lakehouse.layer_lakehouses["silver"].id : null
}

output "gold_lakehouse_id" {
  description = "ID of the gold lakehouse (if enabled)"
  value       = var.gold_layer && contains(keys(fabric_lakehouse.layer_lakehouses), "gold") ? fabric_lakehouse.layer_lakehouses["gold"].id : null
}

# Notebook Outputs (Updated for predefined notebooks)
output "notebooks" {
  description = "Map of deployed predefined notebooks with their details"
  value = {
    for name, notebook in fabric_notebook.predefined_notebooks : name => {
      id           = notebook.id
      name         = notebook.display_name
      workspace_id = notebook.workspace_id
      url          = "https://app.fabric.microsoft.com/groups/${notebook.workspace_id}/notebooks/${notebook.id}"
      source_path  = var.predefined_notebooks[name].source_path
    }
  }
}

output "notebook_ids" {
  description = "Map of notebook names to their IDs"
  value = {
    for name, notebook in fabric_notebook.predefined_notebooks : name => notebook.id
  }
}

output "notebook_names" {
  description = "Map of notebook keys to their display names in Fabric"
  value = {
    for name, notebook in fabric_notebook.predefined_notebooks : name => notebook.display_name
  }
}

# Pipeline Outputs (Updated for predefined pipeline)
output "pipeline_id" {
  description = "ID of the predefined pipeline (if created)"
  value       = length(fabric_data_pipeline.predefined_pipeline) > 0 ? fabric_data_pipeline.predefined_pipeline[0].id : null
}

output "pipeline_name" {
  description = "Name of the predefined pipeline (if created)"
  value       = length(fabric_data_pipeline.predefined_pipeline) > 0 ? fabric_data_pipeline.predefined_pipeline[0].display_name : null
}

output "pipeline_url" {
  description = "URL to access the predefined pipeline (if created)"
  value       = length(fabric_data_pipeline.predefined_pipeline) > 0 ? "https://app.fabric.microsoft.com/groups/${fabric_data_pipeline.predefined_pipeline[0].workspace_id}/datapipelines/${fabric_data_pipeline.predefined_pipeline[0].id}" : null
}

output "pipeline_type" {
  description = "Type of predefined pipeline deployed"
  value       = var.predefined_pipeline.enabled ? var.predefined_pipeline.pipeline_type : null
}

# Capacity Assignment Output
output "capacity_assignment_id" {
  description = "ID of the workspace capacity assignment (if created)"
  value       = length(fabric_workspace_capacity_assignment.workspace_capacity) > 0 ? fabric_workspace_capacity_assignment.workspace_capacity[0].id : null
}

# Summary Information for Platform Integration
output "deployment_summary" {
  description = "Summary of deployed resources for platform integration"
  value = {
    customer_name    = var.customer_name
    customer_prefix  = var.customer_prefix
    environment      = var.environment
    workspace_id     = local.workspace_id
    workspace_name   = local.workspace_name
    workspace_created = local.create_workspace
    
    enabled_layers = {
      bronze = var.bronze_layer
      silver = var.silver_layer
      gold   = var.gold_layer
    }
    
    predefined_artifacts = {
      notebooks_deployed = length(var.predefined_notebooks)
      pipeline_deployed  = var.predefined_pipeline.enabled
      pipeline_type      = var.predefined_pipeline.enabled ? var.predefined_pipeline.pipeline_type : null
    }
    
    resource_counts = {
      lakehouses = length(fabric_lakehouse.layer_lakehouses)
      notebooks  = length(fabric_notebook.predefined_notebooks)
      pipelines  = length(fabric_data_pipeline.predefined_pipeline)
    }
    
    capacity_id = var.fabric_capacity_id
    debug_mode  = var.debug_mode
  }
}

# Resource URLs for Quick Access
output "resource_urls" {
  description = "URLs for quick access to deployed resources"
  value = {
    workspace = "https://app.fabric.microsoft.com/groups/${local.workspace_id}"
    
    lakehouses = {
      for layer, lakehouse in fabric_lakehouse.layer_lakehouses : layer => (
        "https://app.fabric.microsoft.com/groups/${lakehouse.workspace_id}/lakehouses/${lakehouse.id}"
      )
    }
    
    notebooks = {
      for name, notebook in fabric_notebook.predefined_notebooks : name => (
        "https://app.fabric.microsoft.com/groups/${notebook.workspace_id}/notebooks/${notebook.id}"
      )
    }
    
    pipeline = length(fabric_data_pipeline.predefined_pipeline) > 0 ? (
      "https://app.fabric.microsoft.com/groups/${fabric_data_pipeline.predefined_pipeline[0].workspace_id}/datapipelines/${fabric_data_pipeline.predefined_pipeline[0].id}"
    ) : null
  }
}

# Configuration Verification Output
output "configuration_status" {
  description = "Status of configuration and deployment validation"
  value = {
    valid_customer_prefix = can(regex("^[a-z0-9]{2,8}$", var.customer_prefix))
    valid_environment     = contains(["dev", "staging", "prod"], var.environment)
    layers_enabled        = length([for layer, enabled in local.enabled_layers : layer if enabled])
    
    # Predefined artifacts status
    predefined_notebooks_count = length(var.predefined_notebooks)
    predefined_pipeline_enabled = var.predefined_pipeline.enabled
    
    capacity_assigned = var.fabric_capacity_id != null
    
    deployment_complete = alltrue([
      local.workspace_id != null,
      length(fabric_lakehouse.layer_lakehouses) > 0,
      length(var.predefined_notebooks) == 0 || length(fabric_notebook.predefined_notebooks) > 0
    ])
  }
}

# Predefined Artifacts Summary
output "predefined_artifacts_summary" {
  description = "Summary of predefined artifacts deployed"
  value = {
    notebooks = {
      for key, config in var.predefined_notebooks : key => {
        source_path    = config.source_path
        deployed_name  = "${var.customer_prefix}-${key}"
        fabric_id      = fabric_notebook.predefined_notebooks[key].id
        custom_tokens  = config.custom_tokens
      }
    }
    
    pipeline = var.predefined_pipeline.enabled ? {
      pipeline_type  = var.predefined_pipeline.pipeline_type
      source_path    = var.predefined_pipeline.source_path
      deployed_name  = local.pipeline_name
      fabric_id      = fabric_data_pipeline.predefined_pipeline[0].id
      custom_tokens  = var.predefined_pipeline.custom_tokens
    } : null
  }
}