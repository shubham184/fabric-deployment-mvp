# fabric_semantic_model (Resource)

The Semantic Model resource allows you to manage a Fabric Semantic Model.

ℹ️ **Note**

This resource supports Service Principal authentication.

## Example Usage

```hcl
# Semantic Model bootstrapping only
resource "fabric_semantic_model" "example_bootstrap" {
  display_name              = "example"
  workspace_id              = "00000000-0000-0000-0000-000000000000"
  definition_update_enabled = false
  format                    = "TMSL"
  definition = {
    "model.bim" = {
      source = "${local.path}/model.bim.tmpl"
    }
    "definition.pbism" = {
      source = "${local.path}/definition.pbism"
    }
  }
}

# Semantic Model with definition update when source or tokens changed
resource "fabric_semantic_model" "example_update" {
  display_name = "example with update"
  workspace_id = "00000000-0000-0000-0000-000000000000"
  format       = "TMSL"
  definition = {
    "model.bim" = {
      source = "${local.path}/model.bim.tmpl"
      tokens = {
        "ColumnName" = "Hello"
      }
    }
    "definition.pbism" = {
      source = "${local.path}/definition.pbism"
    }
  }
}
```

## Schema

### Required

- `definition` (Attributes Map) Definition parts. Read more about [Semantic Model definition part paths](https://registry.terraform.io/providers/microsoft/fabric/latest/docs/guides/definition_paths#semantic-model). Accepted path keys: **TMDL format:** `definition.pbism`, `definition/database.tmdl`, `definition/expressions.tmdl`, `definition/model.tmdl`, `definition/relationships.tmdl`, `definition/tables/*.tmdl`, `diagramLayp.json` **TMSL format:** `definition.pbism`, `diagramLayp.json`, `model.bim` (see [below for nested schema](#nested-schema-for-definition))
- `display_name` (String) The Semantic Model display name.
- `format` (String) The Semantic Model format. Possible values: `TMDL`, `TMSL`
- `workspace_id` (String) The Workspace ID.

### Optional

- `definition_update_enabled` (Boolean) Update definition on change of source content. Default: `true`.
- `description` (String) The Semantic Model description.
- `timeouts` (Attributes) (see [below for nested schema](#nested-schema-for-timeouts))

### Read-Only

- `id` (String) The Semantic Model ID.

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
# terraform import fabric_semantic_model.example "<WorkspaceID>/<SemanticModelID>"
terraform import fabric_semantic_model.example "00000000-0000-0000-0000-000000000000/11111111-1111-1111-1111-111111111111"
```