"""
Helper utility functions for configuration management.

This module provides common utility functions used across the configuration
loading system, including deep merge, YAML loading, and file validation.
"""

import copy
from pathlib import Path
from typing import Any, Dict, Union

import yaml


def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries, with dict2 values overriding dict1.
    
    Nested dictionaries are merged recursively rather than replaced.
    
    Args:
        dict1: Base dictionary
        dict2: Override dictionary
        
    Returns:
        New dictionary with merged values
        
    Example:
        >>> base = {"a": {"x": 1, "y": 2}, "b": 3}
        >>> override = {"a": {"y": 20, "z": 30}, "c": 4}
        >>> deep_merge(base, override)
        {"a": {"x": 1, "y": 20, "z": 30}, "b": 3, "c": 4}
    """
    result = copy.deepcopy(dict1)
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    
    return result


def safe_load_yaml(file_path: Path) -> Dict[str, Any]:
    """
    Safely load YAML file with proper error handling.
    
    Args:
        file_path: Path to YAML file
        
    Returns:
        Parsed YAML content as dictionary
        
    Raises:
        FileNotFoundError: If file doesn't exist
        yaml.YAMLError: If YAML is invalid
        ValueError: If file is empty or doesn't contain a dictionary
    """
    validate_file_exists(file_path, f"YAML file")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = yaml.safe_load(file)
            
        if content is None:
            raise ValueError(f"YAML file is empty: {file_path}")
            
        if not isinstance(content, dict):
            raise ValueError(f"YAML file must contain a dictionary, got {type(content).__name__}: {file_path}")
            
        return content
        
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML in file {file_path}: {str(e)}")


def validate_file_exists(file_path: Path, description: str) -> None:
    """
    Validate that a file exists and provide helpful error message.
    
    Args:
        file_path: Path to validate
        description: Human-readable description for error message
        
    Raises:
        FileNotFoundError: If file doesn't exist with descriptive message
    """
    if not file_path.exists():
        raise FileNotFoundError(
            f"{description} not found at '{file_path}'. "
            f"Please check the path and ensure the file exists."
        )
        
    if not file_path.is_file():
        raise FileNotFoundError(
            f"Expected a file but found directory at '{file_path}'. "
            f"Please check the path."
        )


def merge_tags(*tag_dicts: Dict[str, str]) -> Dict[str, str]:
    """
    Merge multiple tag dictionaries with later ones taking precedence.
    
    Args:
        *tag_dicts: Variable number of tag dictionaries to merge
        
    Returns:
        Merged tag dictionary
        
    Example:
        >>> customer_tags = {"customer": "contoso", "project": "analytics"}
        >>> env_tags = {"environment": "dev", "customer": "contoso-dev"}
        >>> merge_tags(customer_tags, env_tags)
        {"customer": "contoso-dev", "project": "analytics", "environment": "dev"}
    """
    merged = {}
    for tag_dict in tag_dicts:
        if tag_dict:
            merged.update(tag_dict)
    return merged


def normalize_path(path: Union[str, Path]) -> Path:
    """
    Normalize path input to Path object with validation.
    
    Args:
        path: String or Path object
        
    Returns:
        Normalized Path object
        
    Raises:
        ValueError: If path is empty or invalid
    """
    if not path:
        raise ValueError("Path cannot be empty")
        
    path_obj = Path(path)
    return path_obj.resolve()


def ensure_directory_exists(directory: Path) -> None:
    """
    Ensure directory exists, create if it doesn't.
    
    Args:
        directory: Directory path to ensure exists
        
    Raises:
        OSError: If directory cannot be created
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise OSError(f"Failed to create directory {directory}: {str(e)}")