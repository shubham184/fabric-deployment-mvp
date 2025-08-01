# Authenticating using a Service Principal and Client Secret

## Overview

⚠️ **Warning**

We recommend using either a Service Principal with OpenID Connect (OIDC) or Managed Service Identity (MSI) authentication when running Terraform non-interactively (such as when running Terraform in a CI server), and authenticating using the Azure CLI when running Terraform locally.

## Setting up Entra Application and Service Principal

Follow [Creating an App Registration for the Service Principal context (SPN)](https://registry.terraform.io/providers/microsoft/fabric/latest/docs/guides/auth_spn_secret) guide.

## Creating Client Secret

1. In the Microsoft Entra admin center, in App registrations, select your application.

2. Select **Certificates & secrets** > **Client secrets** > **New client secret**.

3. Add a description for your client secret.

4. Select an expiration for the secret or specify a custom lifetime.
   - Client secret lifetime is limited to two years (24 months) or less.
   - You can't specify a custom lifetime longer than 24 months.
   - Microsoft recommends that you set an expiration value of less than 12 months.

5. Select **Add**.

6. Record the secret's value for use in your client application code. This secret value is never displayed again after you leave this page.

For application security recommendations, see [Microsoft identity platform best practices and recommendations](https://docs.microsoft.com/en-us/azure/active-directory/develop/identity-platform-integration-checklist).

## Configuring Terraform to use the Client Secret

### Environment Variables

Our recommended approach is storing the credentials as Environment Variables, for example:

#### sh

```bash
export FABRIC_TENANT_ID="00000000-0000-0000-0000-000000000000"
export FABRIC_CLIENT_ID="00000000-0000-0000-0000-000000000000"
export FABRIC_CLIENT_SECRET="YourClientSecret"
```

#### PowerShell

```powershell
$env:FABRIC_TENANT_ID = '00000000-0000-0000-0000-000000000000'
$env:FABRIC_CLIENT_ID = '00000000-0000-0000-0000-000000000000'
$env:FABRIC_CLIENT_SECRET = 'YourClientSecret'
```

The following Terraform and Provider blocks can be specified, where `0.0.0` is the version of the Fabric Provider that you'd like to use:

```hcl
# We strongly recommend using the required_providers block 
terraform {
  required_version = ">= 1.8, < 2.0"
  required_providers {
    fabric = {
      source = "microsoft/fabric"
      version = "0.0.0" # Check for the latest version on the registry
    }
  }
}

# Configure the Microsoft Fabric Provider
provider "fabric" {}
```

### Provider Block

It's also possible to configure these variables either directly or from variables in your provider block.

The following Terraform and Provider blocks can be specified, where `0.0.0` is the version of the Fabric Provider that you'd like to use:

```hcl
variable "client_secret" {
  description = "The client secret."
  type        = string
  sensitive   = true
}

# We strongly recommend using the required_providers block 
terraform {
  required_version = ">= 1.8, < 2.0"
  required_providers {
    fabric = {
      source = "microsoft/fabric"
      version = "0.0.0" # Check for the latest version on the registry
    }
  }
}

# Configure the Microsoft Fabric Provider
provider "fabric" {
  tenant_id = "00000000-0000-0000-0000-000000000000"
  client_id = "00000000-0000-0000-0000-000000000000"
  client_secret = var.client_secret
}
```

### Creating a "secret.tfvars" file to store your credentials

Alternatively you can create a `secret.tfvars` file and execute the `terraform plan/apply` commands specifying a local variables file:

```bash
# terraform plan command pointing to a secret.tfvars
terraform plan -var-file="secret.tfvars"

# terraform apply command pointing to a secret.tfvars
terraform apply -var-file="secret.tfvars"
```

Below you will find an example of how to create your `secret.tfvars` file, remember to specify the correct path of it when executing. We include "*.tfvars" in `.gitignore` to avoid save the secrets in it repository.

```hcl
# sample "secret.tfvars" values
tenant_id = "00000000-0000-0000-0000-000000000000"
client_id = "00000000-0000-0000-0000-000000000000"
client_secret = "YourClientSecret"
```

In the terraform documentation [Protect sensitive input variables](https://developer.hashicorp.com/terraform/tutorials/configuration-language/sensitive-variables) you can find more examples.

The following Terraform and Provider blocks can be specified, where `0.0.0` is the version of the Fabric Provider that you'd like to use:

```hcl
variable "tenant_id" {
  description = "The tenant id."
  type        = string
}

variable "client_id" {
  description = "The client id."
  type        = string
}

variable "client_secret" {
  description = "The client secret."
  type        = string
  sensitive   = true
}

# We strongly recommend using the required_providers block 
terraform {
  required_version = ">= 1.8, < 2.0"
  required_providers {
    fabric = {
      source = "microsoft/fabric"
      version = "0.0.0" # Check for the latest version on the registry
    }
  }
}

# Configure the Microsoft Fabric Provider
provider "fabric" {
  tenant_id = var.tenant_id
  client_id = var.client_id
  client_secret = var.client_secret
}
```
