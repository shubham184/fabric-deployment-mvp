variable "customer_name" {
  type        = string
  description = "Customer name"
}

variable "customer_prefix" {
  type        = string
  description = "Customer prefix for resource naming"
}

variable "workspace_id" {
  type        = string
  description = "Existing Fabric workspace ID"
}

variable "capacity_id" {
  type        = string
  description = "Fabric capacity ID (for reference only - workspace must be pre-assigned)"
  default     = ""
}

variable "environment" {
  type        = string
  description = "Deployment environment (dev/prod)"
  default     = "dev"
}

variable "bronze_enabled" {
  type        = bool
  description = "Enable bronze layer"
  default     = true
}

variable "silver_enabled" {
  type        = bool
  description = "Enable silver layer"
  default     = true
}

variable "gold_enabled" {
  type        = bool
  description = "Enable gold layer"
  default     = true
}

variable "notebooks" {
  type = map(object({
    display_name = string
    path         = string
  }))
  description = "Notebooks to deploy"
  default     = {}
}

variable "pipelines" {
  type = map(object({
    display_name = string
    path         = string
  }))
  description = "Pipelines to deploy"
  default     = {}
}