# Corrected Provider Configuration based on Microsoft Fabric Provider Documentation
# Addresses authentication, preview features, and best practices

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

# Enhanced Provider configuration with explicit settings
provider "fabric" {
  # Authentication configuration based on environment
  # For production: Use Service Principal (environment variables)
  # For development: Use Azure CLI
  
  # Service Principal Authentication (Recommended for CI/CD)
  # Set these environment variables:
  # FABRIC_TENANT_ID     = "your-tenant-id"
  # FABRIC_CLIENT_ID     = "your-client-id" 
  # FABRIC_CLIENT_SECRET = "your-client-secret"
  
  # Optional: Explicitly set tenant_id if not using environment variables
  # tenant_id = var.tenant_id
  
  # Optional: Enable preview features if needed
  preview = var.enable_preview_features
  
  # Optional: Set custom endpoint if using different cloud
  # environment = "public"  # Options: public, usgovernment, china
  
  # Optional: Set custom timeout for all operations
  timeout = "30m"
  
  # Optional: Disable Terraform Partner ID if needed
  # disable_terraform_partner_id = false
}

# Variables for provider configuration
variable "enable_preview_features" {
  type        = bool
  description = "Enable preview features in Fabric provider"
  default     = false
}

variable "tenant_id" {
  type        = string
  description = "Azure tenant ID (optional if using environment variables)"
  default     = null
  sensitive   = true
}