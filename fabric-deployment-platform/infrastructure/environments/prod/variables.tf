# Production Environment - Variable Definitions
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
  
  validation {
    condition = var.fabric_capacity_id != null && length(var.fabric_capacity_id) > 0
    error_message = "Fabric capacity ID is required for production environment."
  }
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
    environment = "prod"
    project     = "fabric-deployment"
    criticality = "high"
  }
}

# Debug Configuration (from TerraformWrapper)
variable "debug_mode" {
  type        = bool
  description = "Enable debug mode from TerraformWrapper environment setting"
  default     = false # Default to false for production environment
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

# Production Environment Specific Variables
variable "enable_backup" {
  type        = bool
  description = "Enable backup and disaster recovery for production"
  default     = true
}

variable "backup_retention_days" {
  type        = number
  description = "Number of days to retain backups"
  default     = 365
  
  validation {
    condition     = var.backup_retention_days >= 90
    error_message = "Production backup retention must be at least 90 days."
  }
}

# Advanced Configuration Variables (Required for Production)
variable "pipeline_schedule" {
  type = object({
    enabled    = bool
    frequency  = string
    interval   = number
    start_time = string
  })
  description = "Pipeline scheduling configuration for production"
  default = {
    enabled    = true     # Enabled by default in production
    frequency  = "Hour"
    interval   = 1        # Every hour for production
    start_time = "2024-01-01T00:00:00Z"
  }
}

variable "lakehouse_settings" {
  type = object({
    enable_schemas          = bool
    default_schema_name     = string
    enable_delta_lake       = bool
    enable_auto_tune        = bool
  })
  description = "Production lakehouse configuration settings"
  default = {
    enable_schemas      = true
    default_schema_name = "prod_schema"
    enable_delta_lake   = true
    enable_auto_tune    = true   # Enabled for production performance
  }
}

variable "workspace_settings" {
  type = object({
    enable_git_integration = bool
    git_repository_url     = string
    git_branch            = string
    enable_monitoring     = bool
  })
  description = "Production workspace configuration settings"
  default = {
    enable_git_integration = true    # Enable for production
    git_repository_url     = ""      # Must be provided for production
    git_branch            = "main"   # Production branch
    enable_monitoring     = true
  }
  
  validation {
    condition = var.workspace_settings.enable_git_integration == false || length(var.workspace_settings.git_repository_url) > 0
    error_message = "Git repository URL is required when git integration is enabled in production."
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
  description = "Optional resource name overrides for production environment"
  default = {
    workspace_name = ""
    bronze_lakehouse_name = ""
    silver_lakehouse_name = ""
    gold_lakehouse_name = ""
    pipeline_name = ""
  }
}

# Production Security and Compliance Variables
variable "enable_audit_logging" {
  type        = bool
  description = "Enable comprehensive audit logging"
  default     = true
}

variable "require_mfa" {
  type        = bool
  description = "Require multi-factor authentication"
  default     = true
}

variable "enable_data_encryption" {
  type        = bool
  description = "Enable data encryption at rest and in transit"
  default     = true
}

# Production Validation Variables
variable "validate_notebook_files" {
  type        = bool
  description = "Validate that notebook files exist before deployment"
  default     = true
}

variable "max_deployment_time" {
  type        = number
  description = "Maximum deployment time in minutes for production environment"
  default     = 60
  
  validation {
    condition     = var.max_deployment_time > 0 && var.max_deployment_time <= 180
    error_message = "Max deployment time must be between 1 and 180 minutes."
  }
}

# Production Testing Variables
variable "run_integration_tests" {
  type        = bool
  description = "Run integration tests after deployment"
  default     = true
}

variable "run_performance_tests" {
  type        = bool
  description = "Run performance tests after deployment"
  default     = true
}

# High Availability and Disaster Recovery
variable "enable_high_availability" {
  type        = bool
  description = "Enable high availability configuration"
  default     = true
}

variable "disaster_recovery_region" {
  type        = string
  description = "Secondary region for disaster recovery"
  default     = ""
}