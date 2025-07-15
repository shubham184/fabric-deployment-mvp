# fabric_notebook (Resource)

The Notebook resource allows you to manage a Fabric [Notebook](https://docs.microsoft.com/en-us/fabric/data-engineering/how-to-use-notebook).

ℹ️ **Note**

This resource supports Service Principal authentication.

## Example Usage

```hcl
# Example 1 - Notebook without definition
resource "fabric_notebook" "example" {
  display_name = "example"
  workspace_id = "00000000-0000-0000-0000-000000000000"
}

# Example 2 - Notebook with definition bootstrapping only
resource "fabric_notebook" "example_definition_bootstrap" {
  display_name = "example"
  description  = "example with definition bootstrapping"
  workspace_id = "00000000-0000-0000-0000-000000000000"
  definition_update_enabled = false
  format = "ipynb"
  definition = {
    "notebook-content.ipynb" = {
      source = "${local.path}/notebook.ipynb.tmpl"
    }
  }
}

# Example 3 - Notebook with definition update when source changes
resource "fabric_notebook" "example_definition_update" {
  display_name = "example"
  description  = "example with definition update when source changes"
  workspace_id = "00000000-0000-0000-0000-000000000000"
  format = "ipynb"
  definition = {
    "notebook-content.ipynb" = {
      source = "${local.path}/notebook.ipynb.tmpl"
      tokens = {
        "MESSAGE" = "World"
        "MyValue" = "Lorem Ipsum"
      }
    }
  }
}
```

## Schema

### Required

- `display_name` (String) The Notebook display name.
- `workspace_id` (String) The Workspace ID.

### Optional

- `definition` (Attributes Map) Definition parts. Read more about [Notebook definition part paths](https://registry.terraform.io/providers/microsoft/fabric/latest/docs/guides/definition_paths#notebook). Accepted path keys: **ipynb format:** `notebook-content.ipynb` **py format:** `notebook-content.py` (see [below for nested schema](#nested-schema-for-definition))
- `definition_update_enabled` (Boolean) Update definition on change of source content. Default: `true`.
- `description` (String) The Notebook description.
- `format` (String) The Notebook format. Possible values: `ipynb`, `py`
- `timeouts` (Attributes) (see [below for nested schema](#nested-schema-for-timeouts))

### Read-Only

- `id` (String) The Notebook ID.

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
# terraform import fabric_notebook.example "<WorkspaceID>/<NotebookID>"
terraform import fabric_notebook.example "00000000-0000-0000-0000-000000000000/11111111-1111-1111-1111-111111111111"
```