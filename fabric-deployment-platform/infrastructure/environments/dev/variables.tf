# Development Environment - Variable Definitions (MISSING VARIABLES ADDED)
# Variables that map to TerraformWrapper output and ConfigLoader configuration

# Customer Information Variables (from TerraformWrapper)
variable "customer_name" {
  type        = string
  description = "Full customer name from ConfigLoader"
  
  validation {
    condition     = length(var.customer_name) > 0
    error_message = "Customer name cannot be empty."
  }
}

variable "customer_prefix" {
  type        = string
  description = "Customer prefix for resource naming from ConfigLoader"
  
  validation {
    condition     = can(regex("^[a-z0-9]{2,8}$", var.customer_prefix))
    error_message = "Customer prefix must be 2-8 characters, lowercase letters and numbers only."
  }
}

# Infrastructure Variables (from TerraformWrapper)
variable "workspace_id" {
  type        = string
  description = "Existing workspace ID from ConfigLoader (optional)"
  default     = null
  
  validation {
    condition = var.workspace_id == null || var.workspace_id == "" || can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", var.workspace_id))
    error_message = "Workspace ID must be a valid GUID format when provided."
  }
}

variable "fabric_capacity_id" {
  type        = string
  description = "Microsoft Fabric capacity ID from ConfigLoader"
  default     = null
}

# Medallion Architecture Configuration (from ConfigLoader)
variable "bronze_layer" {
  type        = bool
  description = "Enable bronze layer from ConfigLoader medallion configuration"
  default     = true
}

variable "silver_layer" {
  type        = bool
  description = "Enable silver layer from ConfigLoader medallion configuration"
  default     = true
}

variable "gold_layer" {
  type        = bool
  description = "Enable gold layer from ConfigLoader medallion configuration"
  default     = true
}

# Resource Tagging (from TerraformWrapper)
variable "tags" {
  type        = map(string)
  description = "Resource tags from TerraformWrapper"
  default = {
    environment = "dev"
    project     = "mvp-fabric-deployment"
  }
}

# Debug Configuration (from TerraformWrapper)
variable "debug_mode" {
  type        = bool
  description = "Enable debug mode from TerraformWrapper environment setting"
  default     = true # Default to true for development environment
}

# Notebook Files Configuration
variable "notebook_files_override" {
  type        = map(string)
  description = "Override notebook files mapping (if not using auto-discovery)"
  default     = {}
  
  validation {
    condition = alltrue([
      for path in values(var.notebook_files_override) : can(regex(".*\\.ipynb$", path))
    ])
    error_message = "All notebook file paths must end with .ipynb extension."
  }
}

# Development Environment Specific Variables
variable "dev_admin_users" {
  type = list(object({
    principal_id   = string
    principal_type = string
  }))
  description = "List of users to grant Admin access to the development workspace"
  default     = []
  
  validation {
    condition = alltrue([
      for user in var.dev_admin_users : contains(["User", "Group", "ServicePrincipal"], user.principal_type)
    ])
    error_message = "Principal type must be one of: User, Group, ServicePrincipal."
  }
}

variable "dev_contributor_users" {
  type = list(object({
    principal_id   = string
    principal_type = string
  }))
  description = "List of users to grant Contributor access to the development workspace"
  default     = []
  
  validation {
    condition = alltrue([
      for user in var.dev_contributor_users : contains(["User", "Group", "ServicePrincipal"], user.principal_type)
    ])
    error_message = "Principal type must be one of: User, Group, ServicePrincipal."
  }
}

variable "enable_dev_features" {
  type        = bool
  description = "Enable development-specific features and monitoring"
  default     = true
}

# ADDED: Missing variable declaration
variable "enable_preview_features" {
  type        = bool
  description = "Enable preview features for development environment"
  default     = false
}

# Advanced Configuration Variables (Optional)
variable "pipeline_schedule" {
  type = object({
    enabled    = bool
    frequency  = string
    interval   = number
    start_time = string
  })
  description = "Pipeline scheduling configuration for development"
  default = {
    enabled    = false  # Disabled by default in development
    frequency  = "Hour"
    interval   = 6      # Every 6 hours for development
    start_time = "2024-01-01T09:00:00Z"
  }
}

variable "lakehouse_settings" {
  type = object({
    enable_schemas          = bool
    default_schema_name     = string
    enable_delta_lake       = bool
    enable_auto_tune        = bool
  })
  description = "Development lakehouse configuration settings"
  default = {
    enable_schemas      = true
    default_schema_name = "dev_schema"
    enable_delta_lake   = true
    enable_auto_tune    = false  # Disabled for predictable development behavior
  }
}

variable "workspace_settings" {
  type = object({
    enable_git_integration = bool
    git_repository_url     = string
    git_branch            = string
    enable_monitoring     = bool
  })
  description = "Development workspace configuration settings"
  default = {
    enable_git_integration = true   # Enable for development
    git_repository_url     = ""     # To be provided if git integration is enabled
    git_branch            = "dev"   # Development branch
    enable_monitoring     = true
  }
}

variable "resource_name_overrides" {
  type = object({
    workspace_name = string
    bronze_lakehouse_name = string
    silver_lakehouse_name = string
    gold_lakehouse_name = string
    pipeline_name = string
  })
  description = "Optional resource name overrides for development environment"
  default = {
    workspace_name = ""
    bronze_lakehouse_name = ""
    silver_lakehouse_name = ""
    gold_lakehouse_name = ""
    pipeline_name = ""
  }
}

# Development Environment Validation Variables
variable "validate_notebook_files" {
  type        = bool
  description = "Validate that notebook files exist before deployment"
  default     = true
}

variable "max_deployment_time" {
  type        = number
  description = "Maximum deployment time in minutes for development environment"
  default     = 30
  
  validation {
    condition     = var.max_deployment_time > 0 && var.max_deployment_time <= 120
    error_message = "Max deployment time must be between 1 and 120 minutes."
  }
}

# Integration Testing Variables
variable "run_integration_tests" {
  type        = bool
  description = "Run integration tests after deployment"
  default     = false
}

variable "test_data_path" {
  type        = string
  description = "Path to test data for integration testing"
  default     = ""
}

# ADDED: Missing variable declarations for development environment  
variable "auto_cleanup_after_tests" {
  type        = bool
  description = "Automatically cleanup resources after testing"
  default     = false
}

# Additional development environment variables
variable "cleanup_retention_hours" {
  type        = number
  description = "Hours to retain test resources before cleanup"
  default     = 24
  
  validation {
    condition     = var.cleanup_retention_hours > 0 && var.cleanup_retention_hours <= 168
    error_message = "Cleanup retention must be between 1 and 168 hours (1 week)."
  }
}

# ADDED: Missing variable declarations for notebook custom tokens
variable "bronze_data_source" {
  type        = string
  description = "Data source connection string for bronze layer ingestion"
  default     = ""
  
  validation {
    condition     = var.bronze_data_source == "" || length(var.bronze_data_source) > 0
    error_message = "Bronze data source cannot be empty if provided."
  }
}

variable "transformation_config" {
  type        = string
  description = "Transformation rules configuration for silver layer"
  default     = "default"
  
  validation {
    condition     = length(var.transformation_config) > 0
    error_message = "Transformation config cannot be empty."
  }
}

variable "dashboard_endpoint" {
  type        = string
  description = "Dashboard endpoint URL for gold layer analytics"
  default     = ""
  
  validation {
    condition     = var.dashboard_endpoint == "" || can(regex("^https?://", var.dashboard_endpoint))
    error_message = "Dashboard endpoint must be a valid URL starting with http:// or https://."
  }
}

variable "admin_email" {
  type        = string
  description = "Admin email address for pipeline notifications and error alerts"
  default     = ""
  
  validation {
    condition     = var.admin_email == "" || can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.admin_email))
    error_message = "Admin email must be a valid email address format."
  }
}