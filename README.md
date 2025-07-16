# Fabric Deployment Platform - MVP

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

# Install dependencies
pip install -r requirements.txt

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
# Deploy to development
python scripts/deploy.py yourcustomer --environment dev

# Deploy to production with auto-approve
python scripts/deploy.py yourcustomer --environment prod --auto-approve
```

## How It Works

1. **Configuration**: Single YAML file per customer defines what to deploy
2. **Artifacts**: Predefined notebooks and pipelines (no dynamic generation)
3. **Terraform**: Handles actual deployment to Fabric workspace
4. **Python**: Simple orchestration - reads config, validates files, runs Terraform

## Architecture

```
Customer Config (YAML)
    ↓
Python Script (deploy.py)
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

## Next Steps (Post-MVP)

1. Add Azure DevOps pipeline
2. Service Principal authentication
3. Workspace creation capability
4. Multiple environment support

## Troubleshooting

### Common Issues

1. **"Workspace not found"**
   - Verify workspace ID in config
   - Ensure you have access to the workspace
   - Check that Service Principal has permissions

2. **"Notebook file not found"**
   - Check path in config matches actual file location
   - Paths are relative to project root

3. **"Terraform init failed"**
   - Ensure Terraform is installed
   - Check Service Principal credentials in secrets.tfvars

4. **"Workspace not assigned to capacity"**
   - The Fabric provider requires workspaces to be pre-assigned to a capacity
   - Assign the workspace to a capacity in Azure Portal before deployment
   - The capacity_id in config is for reference only

### Debug Mode

Run with debug output:
```bash
export TF_LOG=DEBUG
python scripts/deploy.py yourcustomer -e dev
```