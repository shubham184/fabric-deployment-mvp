# Customer Solution Module - Variable Definitions
# Variables that integrate with existing ConfigLoader and TerraformWrapper

# Customer Information
variable "customer_name" {
  type        = string
  description = "Full customer name (e.g., 'Contoso Corp')"
  
  validation {
    condition     = length(var.customer_name) > 0
    error_message = "Customer name cannot be empty."
  }
}

variable "customer_prefix" {
  type        = string
  description = "Customer prefix for resource naming (e.g., 'ctso')"
  
  validation {
    condition     = can(regex("^[a-z0-9]{2,8}$", var.customer_prefix))
    error_message = "Customer prefix must be 2-8 characters, lowercase letters and numbers only."
  }
}

# Environment Configuration
variable "environment" {
  type        = string
  description = "Environment name (dev, staging, prod)"
  default     = "dev"
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

# Workspace Configuration
variable "workspace_id" {
  type        = string
  description = "Existing workspace ID (optional - if not provided, new workspace will be created)"
  default     = null
  
  validation {
    condition = var.workspace_id == null || can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", var.workspace_id))
    error_message = "Workspace ID must be a valid GUID format when provided."
  }
}

# Capacity Configuration
variable "fabric_capacity_id" {
  type        = string
  description = "Microsoft Fabric capacity ID for workspace assignment"
  default     = null
  
  validation {
    condition = var.fabric_capacity_id == null || length(var.fabric_capacity_id) > 0
    error_message = "Fabric capacity ID cannot be empty when provided."
  }
}

# Medallion Architecture Layer Configuration
variable "bronze_layer" {
  type        = bool
  description = "Enable bronze layer lakehouse and resources"
  default     = true
}

variable "silver_layer" {
  type        = bool
  description = "Enable silver layer lakehouse and resources"
  default     = true
}

variable "gold_layer" {
  type        = bool
  description = "Enable gold layer lakehouse and resources"
  default     = true
}

# Notebook File Configuration
variable "notebook_files" {
  type        = map(string)
  description = "Map of notebook names to file paths for deployment"
  default     = {}
  
  validation {
    condition = alltrue([
      for path in values(var.notebook_files) : can(regex(".*\\.ipynb$", path))
    ])
    error_message = "All notebook file paths must end with .ipynb extension."
  }
}

# Resource Tagging
variable "tags" {
  type        = map(string)
  description = "Resource tags to apply to all resources"
  default     = {}
}

# Debug and Development Settings
variable "debug_mode" {
  type        = bool
  description = "Enable debug mode for additional logging and validation"
  default     = false
}

# Pipeline Configuration
variable "pipeline_schedule" {
  type = object({
    enabled    = bool
    frequency  = string
    interval   = number
    start_time = string
  })
  description = "Pipeline scheduling configuration"
  default = {
    enabled    = false
    frequency  = "Hour"
    interval   = 1
    start_time = "2024-01-01T00:00:00Z"
  }
  
  validation {
    condition = contains(["Minute", "Hour", "Day", "Week", "Month"], var.pipeline_schedule.frequency)
    error_message = "Pipeline frequency must be one of: Minute, Hour, Day, Week, Month."
  }
  
  validation {
    condition = var.pipeline_schedule.interval > 0 && var.pipeline_schedule.interval <= 1000
    error_message = "Pipeline interval must be between 1 and 1000."
  }
}

# Advanced Configuration Options
variable "lakehouse_settings" {
  type = object({
    enable_schemas          = bool
    default_schema_name     = string
    enable_delta_lake       = bool
    enable_auto_tune        = bool
  })
  description = "Advanced lakehouse configuration settings"
  default = {
    enable_schemas      = true
    default_schema_name = "default"
    enable_delta_lake   = true
    enable_auto_tune    = true
  }
}

variable "workspace_settings" {
  type = object({
    enable_git_integration = bool
    git_repository_url     = string
    git_branch            = string
    enable_monitoring     = bool
  })
  description = "Advanced workspace configuration settings"
  default = {
    enable_git_integration = false
    git_repository_url     = ""
    git_branch            = "main"
    enable_monitoring     = true
  }
}

# Resource Naming Override (Optional)
variable "resource_name_overrides" {
  type = object({
    workspace_name = string
    bronze_lakehouse_name = string
    silver_lakehouse_name = string
    gold_lakehouse_name = string
    pipeline_name = string
  })
  description = "Optional resource name overrides (if not provided, will use standard naming convention)"
  default = {
    workspace_name = ""
    bronze_lakehouse_name = ""
    silver_lakehouse_name = ""
    gold_lakehouse_name = ""
    pipeline_name = ""
  }
}