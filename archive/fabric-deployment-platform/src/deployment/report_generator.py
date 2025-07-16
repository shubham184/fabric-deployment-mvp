"""
Deployment report generation for Azure DevOps pipeline integration.

This module provides the ReportGenerator class that creates comprehensive
deployment reports in multiple formats for pipeline artifacts, test results,
and deployment documentation.
"""

import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .models import (
    BatchDeploymentResult, DeploymentReport, DeploymentResult, TerraformPlan,
    ValidationResult, PipelineConfig
)
from ..utils.logger import get_logger, log_config_operation, log_config_error


class ReportGenerator:
    """
    Generates deployment reports for pipeline integration.
    
    This class creates comprehensive reports in multiple formats including
    JSON for automation, JUnit XML for test results, and Markdown for
    human-readable documentation.
    """
    
    def __init__(self, output_dir: Path):
        """
        Initialize report generator.
        
        Args:
            output_dir: Directory to save generated reports
            
        Example:
            >>> generator = ReportGenerator(Path("deployment-outputs/reports"))
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(__name__)
        
        log_config_operation(
            self.logger, "INIT_REPORT_GENERATOR",
            f"output_dir={self.output_dir}"
        )
    
    def generate_deployment_report(self, result: DeploymentResult) -> DeploymentReport:
        """
        Generate comprehensive deployment report.
        
        Args:
            result: Deployment result to generate report from
            
        Returns:
            DeploymentReport with all deployment details
            
        Example:
            >>> generator = ReportGenerator(Path("outputs"))
            >>> report = generator.generate_deployment_report(deployment_result)
            >>> print(f"Report generated for {report.customer_name}")
        """
        try:
            # Create artifacts summary
            artifacts_summary = {
                "total_artifacts": len(result.artifacts_deployed),
                "notebooks": len([a for a in result.artifacts_deployed if "notebook" in a.lower()]),
                "lakehouses": len([a for a in result.artifacts_deployed if "lakehouse" in a.lower()]),
                "pipelines": len([a for a in result.artifacts_deployed if "pipeline" in a.lower()])
            }
            
            # Create Terraform summary
            terraform_summary = {
                "outputs_count": len(result.terraform_outputs),
                "workspace_id": result.workspace_id,
                "has_outputs": len(result.terraform_outputs) > 0
            }
            
            # Create validation summary
            validation_summary = {
                "phases_completed": len(result.phases_completed),
                "total_phases": 5,  # Standard deployment phases
                "success_rate": len(result.phases_completed) / 5 if len(result.phases_completed) > 0 else 0
            }
            
            # Create performance metrics
            performance_metrics = {
                "deployment_time_seconds": result.deployment_time,
                "deployment_time_minutes": result.deployment_time / 60,
                "artifacts_per_minute": len(result.artifacts_deployed) / (result.deployment_time / 60) if result.deployment_time > 0 else 0,
                "status": result.status.value
            }
            
            report = DeploymentReport(
                customer_name=result.customer_name,
                environment=result.environment,
                deployment_result=result,
                artifacts_summary=artifacts_summary,
                terraform_summary=terraform_summary,
                validation_summary=validation_summary,
                performance_metrics=performance_metrics
            )
            
            log_config_operation(
                self.logger, "GENERATE_DEPLOYMENT_REPORT",
                f"customer={result.customer_name}, environment={result.environment}, "
                f"success={result.success}"
            )
            
            return report
            
        except Exception as e:
            log_config_error(
                self.logger, "GENERATE_DEPLOYMENT_REPORT", e,
                f"customer={result.customer_name}"
            )
            raise
    
    def generate_terraform_plan_report(self, plan: TerraformPlan) -> Dict[str, Any]:
        """
        Generate Terraform plan report.
        
        Args:
            plan: Terraform plan to generate report from
            
        Returns:
            Dictionary with plan report details
            
        Example:
            >>> generator = ReportGenerator(Path("outputs"))
            >>> plan_report = generator.generate_terraform_plan_report(tf_plan)
        """
        try:
            plan_report = {
                "customer_name": plan.customer_name,
                "environment": plan.environment,
                "has_changes": plan.has_changes,
                "changes_summary": plan.changes,
                "resources_affected": len(plan.resources),
                "resource_list": plan.resources,
                "plan_file_exists": plan.plan_file is not None and plan.plan_file.exists() if plan.plan_file else False,
                "generated_at": datetime.now().isoformat()
            }
            
            log_config_operation(
                self.logger, "GENERATE_PLAN_REPORT",
                f"customer={plan.customer_name}, environment={plan.environment}, "
                f"has_changes={plan.has_changes}"
            )
            
            return plan_report
            
        except Exception as e:
            log_config_error(
                self.logger, "GENERATE_PLAN_REPORT", e,
                f"customer={plan.customer_name}"
            )
            raise
    
    def generate_validation_report(self, validation: ValidationResult, 
                                 context: str = "") -> Dict[str, Any]:
        """
        Generate validation report.
        
        Args:
            validation: Validation result to generate report from
            context: Additional context for the validation
            
        Returns:
            Dictionary with validation report details
            
        Example:
            >>> generator = ReportGenerator(Path("outputs"))
            >>> validation_report = generator.generate_validation_report(validation_result)
        """
        try:
            validation_report = {
                "success": validation.success,
                "context": context,
                "errors_count": len(validation.errors),
                "warnings_count": len(validation.warnings),
                "checks_count": len(validation.checks_performed),
                "errors": validation.errors,
                "warnings": validation.warnings,
                "checks_performed": validation.checks_performed,
                "generated_at": datetime.now().isoformat()
            }
            
            log_config_operation(
                self.logger, "GENERATE_VALIDATION_REPORT",
                f"context={context}, success={validation.success}, "
                f"errors={len(validation.errors)}, warnings={len(validation.warnings)}"
            )
            
            return validation_report
            
        except Exception as e:
            log_config_error(
                self.logger, "GENERATE_VALIDATION_REPORT", e,
                f"context={context}"
            )
            raise
    
    def generate_batch_deployment_report(self, result: BatchDeploymentResult) -> Dict[str, Any]:
        """
        Generate batch deployment report.
        
        Args:
            result: Batch deployment result to generate report from
            
        Returns:
            Dictionary with batch deployment report details
        """
        try:
            # Calculate duration
            duration_seconds = 0
            if result.started_at and result.completed_at:
                duration_seconds = (result.completed_at - result.started_at).total_seconds()
            
            # Create customer summaries
            successful_customers = [dep.customer_name for dep in result.successful_deployments]
            failed_customers = [dep.customer_name for dep in result.failed_deployments]
            
            batch_report = {
                "environment": result.environment,
                "total_customers": result.total_customers,
                "successful_count": result.success_count,
                "failed_count": result.failure_count,
                "success_rate": result.success_count / result.total_customers if result.total_customers > 0 else 0,
                "overall_success": result.overall_success,
                "duration_seconds": duration_seconds,
                "duration_minutes": duration_seconds / 60,
                "successful_customers": successful_customers,
                "failed_customers": failed_customers,
                "started_at": result.started_at.isoformat() if result.started_at else None,
                "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                "generated_at": datetime.now().isoformat()
            }
            
            log_config_operation(
                self.logger, "GENERATE_BATCH_REPORT",
                f"environment={result.environment}, total={result.total_customers}, "
                f"success={result.success_count}, failed={result.failure_count}"
            )
            
            return batch_report
            
        except Exception as e:
            log_config_error(
                self.logger, "GENERATE_BATCH_REPORT", e,
                f"environment={result.environment}"
            )
            raise
    
    def save_pipeline_artifacts(self, reports: List[Dict[str, Any]], 
                               pipeline_config: PipelineConfig) -> None:
        """
        Save all reports as pipeline artifacts.
        
        Args:
            reports: List of report dictionaries to save
            pipeline_config: Pipeline configuration for artifact organization
            
        Example:
            >>> generator = ReportGenerator(Path("outputs"))
            >>> generator.save_pipeline_artifacts(reports, pipeline_config)
        """
        try:
            # Create directory structure
            artifacts_dir = self.output_dir / "pipeline-artifacts"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            
            # Save individual reports
            for i, report in enumerate(reports):
                report_file = artifacts_dir / f"report_{i+1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(report_file, 'w') as f:
                    json.dump(report, f, indent=2)
            
            # Create summary artifact
            summary = {
                "pipeline": {
                    "build_id": pipeline_config.build_id,
                    "source_branch": pipeline_config.source_branch,
                    "repository": pipeline_config.repository,
                    "customer_name": pipeline_config.customer_name,
                    "environment": pipeline_config.environment
                },
                "reports_generated": len(reports),
                "artifacts_location": str(artifacts_dir),
                "generated_at": datetime.now().isoformat()
            }
            
            summary_file = artifacts_dir / "pipeline_summary.json"
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
            
            log_config_operation(
                self.logger, "SAVE_PIPELINE_ARTIFACTS",
                f"reports={len(reports)}, artifacts_dir={artifacts_dir}"
            )
            
        except Exception as e:
            log_config_error(
                self.logger, "SAVE_PIPELINE_ARTIFACTS", e,
                f"reports_count={len(reports)}"
            )
            raise
    
    def to_json(self, report: Dict[str, Any]) -> str:
        """
        Convert report to JSON string.
        
        Args:
            report: Report dictionary to convert
            
        Returns:
            JSON string representation
        """
        try:
            return json.dumps(report, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Failed to convert report to JSON: {e}")
            return "{}"
    
    def to_junit_xml(self, validation: ValidationResult, test_suite_name: str = "deployment_validation") -> str:
        """
        Convert validation result to JUnit XML for test reporting.
        
        Args:
            validation: Validation result to convert
            test_suite_name: Name of the test suite
            
        Returns:
            JUnit XML string
            
        Example:
            >>> generator = ReportGenerator(Path("outputs"))
            >>> junit_xml = generator.to_junit_xml(validation_result, "fabric_deployment")
        """
        try:
            # Create test suite
            testsuite = ET.Element("testsuite")
            testsuite.set("name", test_suite_name)
            testsuite.set("tests", str(len(validation.checks_performed)))
            testsuite.set("failures", str(len(validation.errors)))
            testsuite.set("warnings", str(len(validation.warnings)))
            testsuite.set("time", "0")
            
            # Add test cases for each check
            for check in validation.checks_performed:
                testcase = ET.SubElement(testsuite, "testcase")
                testcase.set("classname", test_suite_name)
                testcase.set("name", check)
                testcase.set("time", "0")
                
                # Add failures if this check had errors
                check_errors = [error for error in validation.errors if check in error.lower()]
                for error in check_errors:
                    failure = ET.SubElement(testcase, "failure")
                    failure.set("message", error)
                    failure.text = error
                
                # Add warnings as system-out
                check_warnings = [warning for warning in validation.warnings if check in warning.lower()]
                if check_warnings:
                    system_out = ET.SubElement(testcase, "system-out")
                    system_out.text = "\n".join(check_warnings)
            
            # Convert to string
            return ET.tostring(testsuite, encoding='unicode')
            
        except Exception as e:
            self.logger.error(f"Failed to convert validation to JUnit XML: {e}")
            return "<testsuite></testsuite>"
    
    def to_markdown(self, report: Dict[str, Any]) -> str:
        """
        Convert report to Markdown for human-readable documentation.
        
        Args:
            report: Report dictionary to convert
            
        Returns:
            Markdown string
            
        Example:
            >>> generator = ReportGenerator(Path("outputs"))
            >>> markdown = generator.to_markdown(deployment_report)
        """
        try:
            lines = []
            
            # Title
            lines.append(f"# Deployment Report")
            lines.append("")
            
            # Basic info
            if "customer_name" in report:
                lines.append(f"**Customer:** {report['customer_name']}")
            if "environment" in report:
                lines.append(f"**Environment:** {report['environment']}")
            if "generated_at" in report:
                lines.append(f"**Generated:** {report['generated_at']}")
            lines.append("")
            
            # Status
            if "success" in report:
                status = "✅ Success" if report["success"] else "❌ Failed"
                lines.append(f"**Status:** {status}")
                lines.append("")
            
            # Artifacts summary
            if "artifacts_summary" in report:
                lines.append("## Artifacts Summary")
                artifacts = report["artifacts_summary"]
                for key, value in artifacts.items():
                    lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
                lines.append("")
            
            # Performance metrics
            if "performance_metrics" in report:
                lines.append("## Performance Metrics")
                metrics = report["performance_metrics"]
                for key, value in metrics.items():
                    if isinstance(value, float):
                        lines.append(f"- **{key.replace('_', ' ').title()}:** {value:.2f}")
                    else:
                        lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
                lines.append("")
            
            # Errors and warnings
            if "errors" in report and report["errors"]:
                lines.append("## Errors")
                for error in report["errors"]:
                    lines.append(f"- ❌ {error}")
                lines.append("")
            
            if "warnings" in report and report["warnings"]:
                lines.append("## Warnings")
                for warning in report["warnings"]:
                    lines.append(f"- ⚠️ {warning}")
                lines.append("")
            
            # Additional sections for specific report types
            if "changes_summary" in report:
                lines.append("## Terraform Changes")
                changes = report["changes_summary"]
                lines.append(f"- **Resources to Add:** {changes.get('add', 0)}")
                lines.append(f"- **Resources to Change:** {changes.get('change', 0)}")
                lines.append(f"- **Resources to Destroy:** {changes.get('destroy', 0)}")
                lines.append("")
            
            return "\n".join(lines)
            
        except Exception as e:
            self.logger.error(f"Failed to convert report to Markdown: {e}")
            return "# Report Generation Failed\n\nAn error occurred while generating the report."
    
    def save_report(self, report: Dict[str, Any], filename: str, 
                   formats: List[str] = None) -> List[Path]:
        """
        Save report in multiple formats.
        
        Args:
            report: Report dictionary to save
            filename: Base filename (without extension)
            formats: List of formats to save ("json", "xml", "md")
            
        Returns:
            List of paths to saved files
            
        Example:
            >>> generator = ReportGenerator(Path("outputs"))
            >>> saved_files = generator.save_report(report, "deployment_report", ["json", "md"])
        """
        if formats is None:
            formats = ["json"]
        
        saved_files = []
        
        try:
            for format_type in formats:
                if format_type == "json":
                    file_path = self.output_dir / f"{filename}.json"
                    with open(file_path, 'w') as f:
                        f.write(self.to_json(report))
                    saved_files.append(file_path)
                
                elif format_type == "md" or format_type == "markdown":
                    file_path = self.output_dir / f"{filename}.md"
                    with open(file_path, 'w') as f:
                        f.write(self.to_markdown(report))
                    saved_files.append(file_path)
                
                elif format_type == "xml" and "checks_performed" in report:
                    # Only save XML for validation reports
                    file_path = self.output_dir / f"{filename}.xml"
                    validation_result = ValidationResult(
                        success=report.get("success", False),
                        errors=report.get("errors", []),
                        warnings=report.get("warnings", []),
                        checks_performed=report.get("checks_performed", [])
                    )
                    with open(file_path, 'w') as f:
                        f.write(self.to_junit_xml(validation_result, filename))
                    saved_files.append(file_path)
            
            log_config_operation(
                self.logger, "SAVE_REPORT",
                f"filename={filename}, formats={formats}, files_saved={len(saved_files)}"
            )
            
        except Exception as e:
            log_config_error(
                self.logger, "SAVE_REPORT", e,
                f"filename={filename}, formats={formats}"
            )
            raise
        
        return saved_files