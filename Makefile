.PHONY: help install test lint format clean deploy validate setup

# Default target
help:
	@echo "Available commands:"
	@echo "  install    - Install dependencies"
	@echo "  test       - Run tests"
	@echo "  lint       - Run linting"
	@echo "  format     - Format code"
	@echo "  clean      - Clean build artifacts"
	@echo "  deploy     - Deploy to environment (usage: make deploy CUSTOMER=customer ENV=dev)"
	@echo "  validate   - Validate configuration (usage: make validate CUSTOMER=customer)"
	@echo "  setup      - Initial setup"

# Install dependencies
install:
	pip install -e .
	pip install -e ".[dev]"

# Run tests
test:
	pytest tests/ -v --cov=src --cov-report=html

# Run linting
lint:
	flake8 src/ tests/ scripts/
	mypy src/

# Format code
format:
	black src/ tests/ scripts/
	isort src/ tests/ scripts/

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

# Deploy to environment
deploy:
	@if [ -z "$(CUSTOMER)" ]; then \
		echo "Error: CUSTOMER is required. Usage: make deploy CUSTOMER=customer ENV=dev"; \
		exit 1; \
	fi
	@if [ -z "$(ENV)" ]; then \
		echo "Error: ENV is required. Usage: make deploy CUSTOMER=customer ENV=dev"; \
		exit 1; \
	fi
	python scripts/deploy.py --customer $(CUSTOMER) --environment $(ENV)

# Validate configuration
validate:
	@if [ -z "$(CUSTOMER)" ]; then \
		echo "Error: CUSTOMER is required. Usage: make validate CUSTOMER=customer"; \
		exit 1; \
	fi
	python scripts/validate.py --customer $(CUSTOMER)

# Render templates
render:
	@if [ -z "$(CUSTOMER)" ]; then \
		echo "Error: CUSTOMER is required. Usage: make render CUSTOMER=customer"; \
		exit 1; \
	fi
	python scripts/render_templates.py --customer $(CUSTOMER)

# Initial setup
setup:
	@echo "Setting up Fabric Deployment Platform..."
	@echo "1. Installing dependencies..."
	make install
	@echo "2. Creating virtual environment..."
	python -m venv venv
	@echo "3. Activating virtual environment..."
	@echo "   Run: source venv/bin/activate"
	@echo "4. Setting up pre-commit hooks..."
	@echo "   Run: pre-commit install"
	@echo "Setup complete!"

# Development server (if applicable)
dev:
	@echo "Starting development server..."
	@echo "Not implemented yet - this would start a local development server"

# Build package
build:
	python -m build

# Install in development mode
dev-install:
	pip install -e ".[dev]"

# Run all checks
check: lint test
	@echo "All checks passed!"

# Docker commands (if needed in future)
docker-build:
	docker build -t fabric-deployment-platform .

docker-run:
	docker run -it fabric-deployment-platform

# Terraform commands
tf-init:
	cd infrastructure/environments/$(ENV) && terraform init

tf-plan:
	cd infrastructure/environments/$(ENV) && terraform plan

tf-apply:
	cd infrastructure/environments/$(ENV) && terraform apply

tf-destroy:
	cd infrastructure/environments/$(ENV) && terraform destroy 