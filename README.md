# Fabric Deployment Platform

A comprehensive platform for automating the deployment of Microsoft Fabric solutions with support for medallion architecture, data pipelines, and customer-specific configurations.

## 🏗️ Architecture Overview

This platform provides a structured approach to deploying Microsoft Fabric solutions with:

- **Medallion Architecture Support**: Bronze, Silver, and Gold layer implementations
- **Template-Based Deployment**: Reusable templates for notebooks, dataflows, pipelines, and more
- **Multi-Environment Support**: Development, Test, and Production environments
- **Customer-Specific Configurations**: Tailored deployments for different customers
- **Infrastructure as Code**: Terraform-based infrastructure management

## 📁 Project Structure

```
fabric-deployment-platform/
├── src/                          # Core Python source code
│   ├── config/                   # Configuration management
│   ├── templates/                # Template rendering and management
│   ├── deployment/               # Deployment orchestration
│   └── utils/                    # Utility functions
├── infrastructure/               # Terraform infrastructure code
│   ├── modules/                  # Reusable Terraform modules
│   ├── environments/             # Environment-specific configurations
│   └── shared/                   # Shared Terraform configurations
├── configs/                      # Configuration files
│   ├── customers/                # Customer-specific configurations
│   ├── defaults/                 # Default configurations
│   └── schemas/                  # JSON schemas for validation
├── scripts/                      # Deployment and utility scripts
├── tests/                        # Unit and integration tests
└── docs/                         # Documentation
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Terraform 1.0+
- Azure CLI
- Microsoft Fabric access

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd fabric-deployment-platform
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your environment:
```bash
cp configs/customers/customer-template configs/customers/your-customer
# Edit configuration files as needed
```

### Basic Usage

1. Validate configuration:
```bash
python scripts/validate.py --customer your-customer
```

2. Deploy to development environment:
```bash
python scripts/deploy.py --customer your-customer --environment dev
```

## 📋 Features

### Core Components

- **Configuration Management**: YAML-based customer configurations with schema validation
- **Template Engine**: Jinja2-based template rendering for Fabric artifacts
- **Deployment Orchestrator**: Automated deployment pipeline management
- **Terraform Integration**: Infrastructure provisioning and management
- **Validation Framework**: Comprehensive validation of configurations and deployments

### Supported Artifacts

- **Notebooks**: Jupyter notebooks for data processing
- **Dataflows**: Power Query data transformation flows
- **Pipelines**: Data Factory pipelines
- **Lakehouses**: OneLake storage configurations
- **Warehouses**: SQL analytics endpoints
- **Semantic Models**: Power BI data models
- **Reports**: Power BI reports and dashboards

## 🔧 Configuration

### Customer Configuration

Each customer has a dedicated configuration directory with:

- `base.yaml`: Core customer settings
- `deploy-order.yaml`: Deployment sequence definition
- `environments/`: Environment-specific overrides

### Environment Support

- **Development**: For development and testing
- **Test**: For staging and validation
- **Production**: For production deployments

## 🧪 Testing

Run the test suite:

```bash
# Unit tests
python -m pytest tests/unit/

# Integration tests
python -m pytest tests/integration/

# All tests with coverage
python -m pytest --cov=src tests/
```

## 📚 Documentation

- [Setup Guide](docs/setup.md)
- [Operations Manual](docs/operations.md)
- [Architecture Overview](docs/architecture.md)
- [API Reference](docs/api-reference.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Check the documentation in the `docs/` directory
- Review the configuration examples in `configs/customers/` 