# Unison Insights Deployment Platform - MVP

A simplified platform for deploying predefined Microsoft Fabric artifacts to customer workspaces.

## Quick Start

### 1. Prerequisites

- Python 3.8+
- Terraform 1.8+
- Service Principal with Fabric permissions
- Access to target Fabric workspace
- **Important**: Workspace must already be assigned to a Fabric capacity

### 2. Setup

```bash
# Clone repository
git clone <repo>
cd fabric-deployment-platform

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the CLI and dependencies
pip install -e .

# Setup Service Principal Authentication
# Copy the example file and fill in your credentials
cp terraform/secrets.tfvars.example terraform/secrets.tfvars
# Edit terraform/secrets.tfvars with your Service Principal details
```

### 3. Configure Customer

Create a configuration file in `configs/customers/yourcustomer.yaml`:

```yaml
customer:
  name: "Your Company"
  prefix: "yc"
  
infrastructure:
  workspace_id: "existing-workspace-guid"
  capacity_id: "existing-capacity-guid"

architecture:
  bronze_enabled: true
  silver_enabled: true
  gold_enabled: true

artifacts:
  notebooks:
    bronze-ingestion:
      display_name: "Bronze Ingestion"
      path: "predefined-artifacts/yourcustomer/notebooks/bronze-ingestion.ipynb"
  pipelines:
    daily-pipeline:
      display_name: "Daily Pipeline"
      path: "predefined-artifacts/yourcustomer/pipelines/daily-pipeline.json"

environments:
  dev:
    debug_mode: true
  prod:
    auto_start_pipeline: true
```

### 4. Add Predefined Artifacts

Place your notebooks and pipelines in:
```
predefined-artifacts/
└── yourcustomer/
    ├── notebooks/
    │   ├── bronze-ingestion.ipynb
    │   └── silver-transform.ipynb
    └── pipelines/
        └── daily-pipeline.json
```

### 5. Deploy

```bash
# Show available commands
unison-insights-deploy --help

# Validate configuration before deployment
unison-insights-deploy validate all yourcustomer --env dev

# Preview what would be deployed (dry-run)
unison-insights-deploy deploy preview yourcustomer --env prod

# Deploy to development
unison-insights-deploy deploy run yourcustomer --env dev

# Deploy to production with auto-approve
unison-insights-deploy deploy run yourcustomer --env prod --auto-approve

# Interactive deployment mode
unison-insights-deploy deploy run yourcustomer --interactive
```

## CLI Commands Overview

### Deploy Commands
```bash
# Run deployment
unison-insights-deploy deploy run <customer> [--env ENV] [--dry-run] [--auto-approve]

# Preview deployment
unison-insights-deploy deploy preview <customer> [--env ENV] [--detailed]
```

### Validation Commands
```bash
# Run all validations
unison-insights-deploy validate all <customer> [--env ENV] [--fix]
```

### Workspace Commands
```bash
# List workspaces
unison-insights-deploy workspace list [--format FORMAT]

# Show workspace info
unison-insights-deploy workspace info <workspace-id> [--artifacts]
```

### Other Commands
```bash
# Initialize new project
unison-insights-deploy init [--customer CUSTOMER] [--template TEMPLATE]

# Show deployment status
unison-insights-deploy status [CUSTOMER]
```

## How It Works

1. **Configuration**: Single YAML file per customer defines what to deploy
2. **Artifacts**: Predefined notebooks and pipelines (no dynamic generation)
3. **CLI**: Beautiful command-line interface with validation and progress tracking
4. **Terraform**: Handles actual deployment to Fabric workspace

## Architecture

```
Customer Config (YAML)
    ↓
Unison Insights Deploy CLI
    ↓
Validation & Orchestration
    ↓
Terraform (main.tf)
    ↓
Microsoft Fabric APIs
```

## What Gets Deployed

- ✅ Lakehouses (Bronze, Silver, Gold)
- ✅ Predefined Notebooks
- ✅ Predefined Pipelines
- ✅ Capacity assignments

## What's NOT in MVP

- ❌ Dynamic artifact generation
- ❌ Template processing
- ❌ Workspace creation (uses existing)
- ❌ Complex configuration inheritance
- ❌ Batch deployments

## Features

### 🔍 Comprehensive Validation
- YAML schema validation
- Resource naming conventions
- Artifact file existence checks
- Workspace access verification
- Capacity assignment validation

### 📊 Deployment Preview
- See what will be deployed before execution
- Resource tree visualization
- Time estimates
- Dry-run mode support

## Next Steps (Post-MVP)

1. Add Azure DevOps pipeline integration
2. Enhanced Service Principal authentication options
3. Workspace creation capability
4. Multiple environment support with inheritance
5. Template-based artifact generation

## Troubleshooting

### Common Issues

1. **"Workspace not found"**
   - Verify workspace ID in config matches your Fabric workspace
   - Ensure Service Principal has access to the workspace
   - Run `unison-insights-deploy validate all <customer>` to check

2. **"Notebook file not found"**
   - Check path in config matches actual file location
   - Paths are relative to project root
   - Validation will show exact missing files

3. **"Terraform init failed"**
   - Ensure Terraform is installed: `terraform --version`
   - Check Service Principal credentials in secrets.tfvars
   - Verify tenant_id, client_id, and client_secret are correct

4. **"Workspace not assigned to capacity"**
   - The Fabric provider requires workspaces to be pre-assigned to a capacity
   - Assign the workspace to a capacity in Azure Portal before deployment
   - The capacity_id in config is for validation only

### Debug Mode

Run with debug output:
```bash
# Enable Terraform debug logs
export TF_LOG=DEBUG

# Run deployment with verbose output
unison-insights-deploy deploy run yourcustomer --env dev
```

### Getting Help

```bash
# General help
unison-insights-deploy --help

# Command-specific help
unison-insights-deploy deploy run --help
unison-insights-deploy validate all --help
```

## Shell Completion

Enable auto-completion for your shell:

```bash
# Install completion
unison-insights-deploy --install-completion

# Follow the instructions for your shell (bash, zsh, fish, PowerShell)
```
