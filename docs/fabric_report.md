# fabric_report (Resource)

The Report resource allows you to manage a Fabric Report.

ℹ️ **Note**

This resource supports Service Principal authentication.

## Example Usage

```hcl
# Report bootstrapping only
resource "fabric_report" "example_bootstrap" {
  display_name              = "example"
  workspace_id              = "00000000-0000-0000-0000-000000000000"
  definition_update_enabled = false
  format                    = "PBIR-Legacy"
  definition = {
    "report.json" = {
      source = "${local.path}/report.json"
    }
    "definition.pbir" = {
      source = "${local.path}/definition.pbir.tmpl"
      tokens = {
        "SemanticModelID" = "00000000-0000-0000-0000-000000000000"
      }
    }
    "StaticResources/SharedResources/BaseThemes/CY24SU10.json" = {
      source = "${local.path}/StaticResources/SharedResources/BaseThemes/CY24SU10.json"
    }
    "StaticResources/RegisteredResources/fabric_48_color10148978481469717.png" = {
      source = "${local.path}/StaticResources/RegisteredResources/fabric_48_color10148978481469717.png"
    }
  }
}

# Report with update when source or tokens changed
resource "fabric_report" "example_update" {
  display_name = "example with update"
  workspace_id = "00000000-0000-0000-0000-000000000000"
  format       = "PBIR-Legacy"
  definition = {
    "report.json" = {
      source = "${local.path}/report.json"
    }
    "definition.pbir" = {
      source = "${local.path}/definition.pbir.tmpl"
      tokens = {
        "SemanticModelID" = "00000000-0000-0000-0000-000000000000"
      }
    }
    "StaticResources/SharedResources/BaseThemes/CY24SU10.json" = {
      source = "${local.path}/StaticResources/SharedResources/BaseThemes/CY24SU10.json"
    }
  }
}
```

## Schema

### Required

- `definition` (Attributes Map) Definition parts. Read more about [Report definition part paths](https://registry.terraform.io/providers/microsoft/fabric/latest/docs/guides/definition_paths#report). Accepted path keys: **PBIR format:** `StaticResources/RegisteredResources/*`, `StaticResources/SharedResources/*`, `definition.pbir`, `definition/pages/*.json`, `definition/report.json`, `definition/version.json` **PBIR-Legacy format:** `StaticResources/RegisteredResources/*`, `StaticResources/SharedResources/*`, `definition.pbir`, `report.json` (see [below for nested schema](#nested-schema-for-definition))
- `display_name` (String) The Report display name.
- `format` (String) The Report format. Possible values: `PBIR`, `PBIR-Legacy`
- `workspace_id` (String) The Workspace ID.

### Optional

- `definition_update_enabled` (Boolean) Update definition on change of source content. Default: `true`.
- `description` (String) The Report description.
- `timeouts` (Attributes) (see [below for nested schema](#nested-schema-for-timeouts))

### Read-Only

- `id` (String) The Report ID.

## Nested Schema for `definition`

### Required:

- `source` (String) Path to the file with source of the definition part.

The source content may include placeholders for token substitution. Use the dot with the token name `{{ .TokenName }}`.

### Optional:

- `tokens` (Map of String) A map of key/value pairs of tokens substitutes in the source.

### Read-Only:

- `source_content_sha256` (String) SHA256 of source's content of definition part.

## Nested Schema for `timeouts`

### Optional:

- `create` (String) A string that can be [parsed as a duration](https://pkg.go.dev/time#ParseDuration) consisting of numbers and unit suffixes, such as "30s" or "2h45m". Valid time units are "s" (seconds), "m" (minutes), "h" (hours).

- `delete` (String) A string that can be [parsed as a duration](https://pkg.go.dev/time#ParseDuration) consisting of numbers and unit suffixes, such as "30s" or "2h45m". Valid time units are "s" (seconds), "m" (minutes), "h" (hours). Setting a timeout for a Delete operation is only applicable if changes are saved into state before the destroy operation occurs.

- `read` (String) A string that can be [parsed as a duration](https://pkg.go.dev/time#ParseDuration) consisting of numbers and unit suffixes, such as "30s" or "2h45m". Valid time units are "s" (seconds), "m" (minutes), "h" (hours). Read operations occur during any refresh or planning operation when refresh is enabled.

- `update` (String) A string that can be [parsed as a duration](https://pkg.go.dev/time#ParseDuration) consisting of numbers and unit suffixes, such as "30s" or "2h45m". Valid time units are "s" (seconds), "m" (minutes), "h" (hours).

## Import

Import is supported using the following syntax:

```bash
# terraform import fabric_report.example "<WorkspaceID>/<ReportID>"
terraform import fabric_report.example "00000000-0000-0000-0000-000000000000/11111111-1111-1111-1111-111111111111"
```