# Shared variables across all environments
variable "default_tags" {
  type = map(string)
  description = "Default tags applied to all resources"
  default = {
    managed_by = "terraform"
    platform   = "fabric-deployment-platform"
  }
}

variable "naming_convention" {
  type = object({
    separator = string
    suffix    = string
  })
  description = "Standard naming convention"
  default = {
    separator = "-"
    suffix    = ""
  }
}