output "workspace_id" {
  description = "The ID of the Fabric workspace"
  value       = data.fabric_workspace.target.id
}

output "lakehouse_ids" {
  description = "IDs of created lakehouses"
  value = {
    bronze = var.bronze_enabled ? fabric_lakehouse.bronze[0].id : null
    silver = var.silver_enabled ? fabric_lakehouse.silver[0].id : null
    gold   = var.gold_enabled ? fabric_lakehouse.gold[0].id : null
  }
}

output "notebook_ids" {
  description = "IDs of deployed notebooks"
  value = {
    for name, notebook in fabric_notebook.notebooks : name => notebook.id
  }
}

output "pipeline_ids" {
  description = "IDs of deployed pipelines"
  value = {
    for name, pipeline in fabric_data_pipeline.pipelines : name => pipeline.id
  }
}

output "deployment_summary" {
  description = "Summary of deployed resources"
  value = {
    customer        = var.customer_name
    environment     = var.environment
    workspace_id    = data.fabric_workspace.target.id
    lakehouses_created = sum([
      var.bronze_enabled ? 1 : 0,
      var.silver_enabled ? 1 : 0,
      var.gold_enabled ? 1 : 0
    ])
    notebooks_deployed = length(fabric_notebook.notebooks)
    pipelines_deployed = length(fabric_data_pipeline.pipelines)
  }
}