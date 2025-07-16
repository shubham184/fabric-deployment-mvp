terraform {
  required_version = ">= 1.8, < 2.0"
  
  required_providers {
    fabric = {
      source  = "microsoft/fabric"
      version = "1.3.0"
    }
  }
}

# Variables for Service Principal authentication
variable "tenant_id" {
  description = "The tenant id"
  type        = string
  sensitive   = true
}

variable "client_id" {
  description = "The client id"
  type        = string
  sensitive   = true
}

variable "client_secret" {
  description = "The client secret"
  type        = string
  sensitive   = true
}

provider "fabric" {
  # Service Principal authentication
  tenant_id     = var.tenant_id
  client_id     = var.client_id
  client_secret = var.client_secret
}

# Data source to verify workspace exists
# Note: This workspace must already be assigned to a Fabric capacity
# Capacity assignment is done through Azure Portal, not Terraform
data "fabric_workspace" "target" {
  id = var.workspace_id
}

# Create Lakehouses based on architecture flags
resource "fabric_lakehouse" "bronze" {
  count = var.bronze_enabled ? 1 : 0
  
  workspace_id = data.fabric_workspace.target.id
  display_name = "${var.customer_prefix}_bronze_lakehouse"
  description  = "Bronze layer lakehouse for ${var.customer_name}"
  
  configuration = {
    enable_schemas = true
  }
}

resource "fabric_lakehouse" "silver" {
  count = var.silver_enabled ? 1 : 0
  
  workspace_id = data.fabric_workspace.target.id
  display_name = "${var.customer_prefix}_silver_lakehouse"
  description  = "Silver layer lakehouse for ${var.customer_name}"
  
  configuration = {
    enable_schemas = true
  }
}

resource "fabric_lakehouse" "gold" {
  count = var.gold_enabled ? 1 : 0
  
  workspace_id = data.fabric_workspace.target.id
  display_name = "${var.customer_prefix}_gold_lakehouse"
  description  = "Gold layer lakehouse for ${var.customer_name}"
  
  configuration = {
    enable_schemas = true
  }
}

# Deploy predefined notebooks
resource "fabric_notebook" "notebooks" {
  for_each = var.notebooks
  
  workspace_id = data.fabric_workspace.target.id
  display_name = each.value.display_name
  description  = "Deployed by Fabric Platform for ${var.customer_name}"
  format       = "ipynb"
  
  definition_update_enabled = true
  
  definition = {
    "notebook-content.ipynb" = {
      source = "${path.root}/../${each.value.path}"
    }
  }
  
  depends_on = [
    fabric_lakehouse.bronze,
    fabric_lakehouse.silver,
    fabric_lakehouse.gold
  ]
}

# Deploy predefined pipelines
resource "fabric_data_pipeline" "pipelines" {
  for_each = var.pipelines
  
  workspace_id = data.fabric_workspace.target.id
  display_name = each.value.display_name
  description  = "Deployed by Fabric Platform for ${var.customer_name}"
  format       = "Default"
  
  definition_update_enabled = true
  
  definition = {
    "pipeline-content.json" = {
      source = "${path.root}/../${each.value.path}"
    }
  }
  
  depends_on = [fabric_notebook.notebooks]
}

# Note: Capacity assignment happens at workspace level in Azure Portal
# The workspace should already be assigned to the capacity