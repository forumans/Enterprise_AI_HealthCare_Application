"""AWS Secrets Manager integration for secure configuration management."""

import os
import json
import logging
import time
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

class AWSSecretsManager:
    """AWS Secrets Manager client for retrieving application secrets."""
    
    def __init__(self, region_name: str = "us-east-1"):
        """Initialize the Secrets Manager client."""
        self.region_name = region_name
        self.client = None
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        self._enabled = os.getenv("AWS_SECRETS_MANAGER_ENABLED").lower() == "true"
        
        if self._enabled:
            try:
                self.client = boto3.client('secretsmanager', region_name=region_name)
                logger.info("AWS Secrets Manager client initialized")
            except (NoCredentialsError, ClientError) as e:
                logger.error(f"Failed to initialize AWS Secrets Manager: {e}")
                self._enabled = False
    
    def is_enabled(self) -> bool:
        """Check if Secrets Manager is enabled and available."""
        return self._enabled and self.client is not None
    
    def get_secret(self, secret_name: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Retrieve a secret from AWS Secrets Manager.
        
        Args:
            secret_name: The name or ARN of the secret
            use_cache: Whether to use cached value if available
            
        Returns:
            The secret value as a dictionary, or None if not found
        """
        if not self.is_enabled():
            logger.warning("AWS Secrets Manager is not enabled")
            return None
            
        # Check cache first
        if use_cache and secret_name in self._cache:
            cached_data = self._cache[secret_name]
            if self._is_cache_valid(cached_data):
                logger.debug(f"Using cached secret for {secret_name}")
                return cached_data['value']
            else:
                # Remove expired cache
                del self._cache[secret_name]
        
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            secret_string = response.get('SecretString')
            
            if secret_string:
                try:
                    # Try to parse as JSON
                    secret_data = json.loads(secret_string)
                except json.JSONDecodeError:
                    # If not JSON, return as string value
                    secret_data = {'value': secret_string}
                
                # Cache the result
                self._cache[secret_name] = {
                    'value': secret_data,
                    'timestamp': time.time()
                }
                
                logger.info(f"Successfully retrieved secret: {secret_name}")
                return secret_data
            else:
                logger.error(f"Secret {secret_name} has no SecretString")
                return None
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                logger.error(f"Secret {secret_name} not found")
            elif error_code == 'InvalidRequestException':
                logger.error(f"Invalid request for secret {secret_name}: {e}")
            elif error_code == 'InvalidParameterException':
                logger.error(f"Invalid parameter for secret {secret_name}: {e}")
            elif error_code == 'DecryptionFailureException':
                logger.error(f"Decryption failed for secret {secret_name}: {e}")
            else:
                logger.error(f"Unknown error retrieving secret {secret_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving secret {secret_name}: {e}")
            return None
    
    def _is_cache_valid(self, cached_data: Dict[str, Any]) -> bool:
        """Check if cached data is still valid."""
        return (time.time() - cached_data['timestamp']) < self._cache_ttl
    
    def get_database_url(self) -> Optional[str]:
        """Get database URL from Secrets Manager."""
        secret_arn = os.getenv("DATABASE_URL_ARN")
        if not secret_arn:
            logger.warning("DATABASE_URL_ARN environment variable not set")
            return None
            
        secret_data = self.get_secret(secret_arn)
        if secret_data:
            return secret_data.get('DATABASE_URL') or secret_data.get('value')
        return None
    
    def get_jwt_secret(self) -> Optional[str]:
        """Get JWT secret from Secrets Manager."""
        secret_arn = os.getenv("JWT_SECRET_ARN")
        if not secret_arn:
            logger.warning("JWT_SECRET_ARN environment variable not set")
            return None
            
        secret_data = self.get_secret(secret_arn)
        if secret_data:
            return secret_data.get('JWT_SECRET') or secret_data.get('value')
        return None
    
    def get_cors_origins(self) -> Optional[str]:
        """Get CORS origins from Secrets Manager."""
        secret_arn = os.getenv("CORS_ORIGINS_ARN")
        if not secret_arn:
            logger.warning("CORS_ORIGINS_ARN environment variable not set")
            return None
            
        secret_data = self.get_secret(secret_arn)
        if secret_data:
            return secret_data.get('CORS_ORIGINS') or secret_data.get('value')
        return None

# Global instance
secrets_manager = AWSSecretsManager()
