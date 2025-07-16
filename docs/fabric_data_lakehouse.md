# fabric_lakehouse (Resource)

The Lakehouse resource allows you to manage a Fabric [Lakehouse](https://docs.microsoft.com/en-us/fabric/data-engineering/lakehouse-overview).

ℹ️ **Note**

This resource supports Service Principal authentication.

## Example Usage

```hcl
# Simple Lakehouse resource
resource "fabric_lakehouse" "example1" {
  display_name = "example1"
  workspace_id = "00000000-0000-0000-0000-000000000000"
}

# Lakehouse resource with enabled schemas
resource "fabric_lakehouse" "example2" {
  display_name = "example2"
  description  = "example2 with enabled schemas"
  workspace_id = "00000000-0000-0000-0000-000000000000"
  configuration = {
    enable_schemas = true
  }
}
```

## Schema

### Required

- `display_name` (String) The Lakehouse display name.
- `workspace_id` (String) The Workspace ID.

### Optional

- `configuration` (Attributes) The Lakehouse creation configuration. Any changes to this configuration will result in recreation of the Lakehouse. (see [below for nested schema](#nested-schema-for-configuration))
- `description` (String) The Lakehouse description.
- `timeouts` (Attributes) (see [below for nested schema](#nested-schema-for-timeouts))

### Read-Only

- `id` (String) The Lakehouse ID.
- `properties` (Attributes) The Lakehouse properties. (see [below for nested schema](#nested-schema-for-properties))

## Nested Schema for `configuration`

### Required Fields

- `enable_schemas` (Boolean) Schema enabled Lakehouse.

## Nested Schema for `timeouts`

### Optional Fields

- `create` (String) A string that can be [parsed as a duration](https://pkg.go.dev/time#ParseDuration) consisting of numbers and unit suffixes, such as "30s" or "2h45m". Valid time units are "s" (seconds), "m" (minutes), "h" (hours).

- `delete` (String) A string that can be [parsed as a duration](https://pkg.go.dev/time#ParseDuration) consisting of numbers and unit suffixes, such as "30s" or "2h45m". Valid time units are "s" (seconds), "m" (minutes), "h" (hours). Setting a timeout for a Delete operation is only applicable if changes are saved into state before the destroy operation occurs.

- `read` (String) A string that can be [parsed as a duration](https://pkg.go.dev/time#ParseDuration) consisting of numbers and unit suffixes, such as "30s" or "2h45m". Valid time units are "s" (seconds), "m" (minutes), "h" (hours). Read operations occur during any refresh or planning operation when refresh is enabled.

- `update` (String) A string that can be [parsed as a duration](https://pkg.go.dev/time#ParseDuration) consisting of numbers and unit suffixes, such as "30s" or "2h45m". Valid time units are "s" (seconds), "m" (minutes), "h" (hours).

## Nested Schema for `properties`

### Read-Only Fields

- `default_schema` (String) Default schema of the Lakehouse. This property is returned only for schema enabled Lakehouse.
- `onelake_files_path` (String) OneLake path to the Lakehouse files directory
- `onelake_tables_path` (String) OneLake path to the Lakehouse tables directory.
- `sql_endpoint_properties` (Attributes) An object containing the properties of the SQL endpoint. (see [below for nested schema](#nested-schema-for-propertiessql_endpoint_properties))

## Nested Schema for `properties.sql_endpoint_properties`

### SQL Endpoint Read-Only Fields

- `connection_string` (String) SQL endpoint connection string.
- `id` (String) SQL endpoint ID.
- `provisioning_status` (String) The SQL endpoint provisioning status.

## Import

Import is supported using the following syntax:

```bash
# terraform import fabric_lakehouse.example "<WorkspaceID>/<LakehouseID>"
terraform import fabric_lakehouse.example "00000000-0000-0000-0000-000000000000/11111111-1111-1111-1111-111111111111"
```
