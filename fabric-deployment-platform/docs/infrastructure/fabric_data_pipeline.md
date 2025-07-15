# fabric_data_pipeline (Resource)

The Data Pipeline resource allows you to manage a Fabric [Data Pipeline](https://docs.microsoft.com/en-us/fabric/data-factory/create-first-pipeline-with-sample-data).

ℹ️ **Note**

This resource supports Service Principal authentication.

## Example Usage

```hcl
# Example 1 - Data Pipeline without definition
resource "fabric_data_pipeline" "example" {
  display_name = "example"
  workspace_id = "00000000-0000-0000-0000-000000000000"
}

# Example 2 - Data Pipeline with definition bootstrapping 
resource "fabric_data_pipeline" "example_definition_bootstrap" {
  display_name = "example"
  description  = "example with definition bootstrapping"
  workspace_id = "00000000-0000-0000-0000-000000000000"
  format = "Default"
  definition_update_enabled = false
  definition = {
    "pipeline-content.json" = {
      source = "${local.path}/pipeline-content.json"
      tokens = {
        "MyValue" = "World"
      }
    }
  }
}

# Example 3 - Data Pipeline with definition update when source changes
resource "fabric_data_pipeline" "example_definition_update" {
  display_name = "example"
  description  = "example with definition update when source changes"
  workspace_id = "00000000-0000-0000-0000-000000000000"
  format = "Default"
  definition = {
    "pipeline-content.json" = {
      source = "${local.path}/pipeline-content.json"
      tokens = {
        "MyValue" = "World"
      }
    }
  }
}
```

## Schema

### Required

- `display_name` (String) The Data Pipeline display name.
- `workspace_id` (String) The Workspace ID.

### Optional

- `definition` (Attributes Map) Definition parts. Read more about [Data Pipeline definition part paths](https://registry.terraform.io/providers/microsoft/fabric/latest/docs/guides/definition_paths#data-pipeline). Accepted path keys: **Default format:** `pipeline-content.json` (see [below for nested schema](#nested-schema-for-definition))
- `definition_update_enabled` (Boolean) Update definition on change of source content. Default: `true`.
- `description` (String) The Data Pipeline description.
- `format` (String) The Data Pipeline format. Possible values: `Default`
- `timeouts` (Attributes) (see [below for nested schema](#nested-schema-for-timeouts))

### Read-Only

- `id` (String) The Data Pipeline ID.

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
# terraform import fabric_data_pipeline.example "<WorkspaceID>/<DataPipelineID>"
terraform import fabric_data_pipeline.example "00000000-0000-0000-0000-000000000000/11111111-1111-1111-1111-111111111111"
```