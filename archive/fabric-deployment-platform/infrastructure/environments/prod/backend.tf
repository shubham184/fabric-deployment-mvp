terraform {
  backend "azurerm" {
    # Configure based on your Azure storage setup
    # These can be set via environment variables or backend config files
    # Example:
    # resource_group_name  = "terraform-state-rg"
    # storage_account_name = "terraformstateXXXXX"
    # container_name       = "tfstate"
    # key                  = "fabric-prod.tfstate"
  }
}