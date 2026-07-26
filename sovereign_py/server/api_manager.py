"""
API Connection Manager for ML Filesystem v1.8+

Manages multiple API connections with:
- Enable/disable without deletion
- Connection testing
- Usage tracking
- Multiple services (AI, streaming, social, etc.)
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
import requests
import json

from core.database import db
from core.enhanced_models import APIConnection, ServiceType
from core.exceptions import APIException


class APIConnectionManager:
    """
    Manages API connections to various services.
    
    Features:
    - Multiple connections per service type
    - Enable/disable toggles
    - Connection testing
    - Usage tracking
    - Safe credential storage
    """
    
    def __init__(self):
        self.session = requests.Session()
    
    def create_connection(
        self,
        name: str,
        service_type: str,
        provider: str,
        api_key: str,
        owner_id: int,
        description: str = None,
        base_url: str = None,
        model_name: str = None,
        config: Dict = None
    ) -> APIConnection:
        """
        Create a new API connection.
        
        Args:
            name: User-friendly name (e.g., "My Claude API")
            service_type: Type of service (ai_inference, streaming, etc.)
            provider: Provider name (e.g., "Anthropic", "OpenAI")
            api_key: API key
            owner_id: User ID
            description: Optional description
            base_url: API base URL
            model_name: Default model
            config: Additional configuration
            
        Returns:
            Created APIConnection
        """
        session = db.get_session()
        try:
            # Validate service type
            try:
                service_type_enum = ServiceType[service_type.upper()]
            except KeyError:
                service_type_enum = ServiceType.CUSTOM
            
            connection = APIConnection(
                name=name,
                description=description,
                service_type=service_type_enum,
                provider=provider,
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                config=config or {},
                owner_id=owner_id,
                enabled=True
            )
            
            session.add(connection)
            session.commit()
            session.refresh(connection)
            
            print(f"✓ Created API connection: {name} ({provider})")
            return connection
        finally:
            session.close()
    
    def get_best_connection(
        self,
        task_type: str = "general",
        owner_id: int = None
    ) -> Optional[APIConnection]:
        """
        Pick the best enabled AI-inference connection for a task.

        Simple priority policy: most-recently-used enabled AI_INFERENCE
        connection wins (proxy for "known good"); falls back to the first
        enabled one, then to any enabled connection at all if none are
        tagged as AI inference.

        Args:
            task_type: Type of task being routed (informational; connections
                don't currently carry per-task-type scoring)
            owner_id: Filter by owner

        Returns:
            Best APIConnection, or None if none are enabled
        """
        connections = self.list_connections(
            owner_id=owner_id,
            service_type='ai_inference',
            enabled_only=True
        )

        if not connections:
            connections = self.list_connections(owner_id=owner_id, enabled_only=True)

        if not connections:
            return None

        connections.sort(key=lambda c: c.last_used or datetime.min, reverse=True)
        return connections[0]

    def get_connection(self, connection_id: int) -> Optional[APIConnection]:
        """Get API connection by ID."""
        session = db.get_session()
        try:
            return session.query(APIConnection).filter_by(id=connection_id).first()
        finally:
            session.close()
    
    def list_connections(
        self,
        owner_id: int = None,
        service_type: str = None,
        enabled_only: bool = False
    ) -> List[APIConnection]:
        """
        List API connections with filters.
        
        Args:
            owner_id: Filter by owner
            service_type: Filter by service type
            enabled_only: Only enabled connections
            
        Returns:
            List of APIConnection objects
        """
        session = db.get_session()
        try:
            query = session.query(APIConnection)
            
            if owner_id:
                query = query.filter_by(owner_id=owner_id)
            
            if service_type:
                try:
                    service_type_enum = ServiceType[service_type.upper()]
                    query = query.filter_by(service_type=service_type_enum)
                except KeyError:
                    pass
            
            if enabled_only:
                query = query.filter_by(enabled=True)
            
            return query.all()
        finally:
            session.close()
    
    def toggle_connection(self, connection_id: int, enabled: bool = None) -> bool:
        """
        Enable or disable a connection.
        
        Args:
            connection_id: Connection ID
            enabled: True to enable, False to disable, None to toggle
            
        Returns:
            New enabled state
        """
        session = db.get_session()
        try:
            connection = session.query(APIConnection).filter_by(id=connection_id).first()
            if not connection:
                return False
            
            if enabled is None:
                connection.enabled = not connection.enabled
            else:
                connection.enabled = enabled
            
            session.commit()
            
            status = "enabled" if connection.enabled else "disabled"
            print(f"✓ API connection '{connection.name}' {status}")
            return connection.enabled
        finally:
            session.close()
    
    def test_connection(self, connection_id: int) -> Dict[str, Any]:
        """
        Test an API connection.
        
        Returns:
            Test results with status and message
        """
        session = db.get_session()
        try:
            connection = session.query(APIConnection).filter_by(id=connection_id).first()
            if not connection:
                return {'status': 'error', 'message': 'Connection not found'}
            
            # Update test timestamp
            connection.last_tested = datetime.utcnow()
            
            # Test based on service type
            result = self._test_by_service_type(connection)
            
            # Update test status
            connection.test_status = result['status']
            connection.test_message = result['message']
            
            session.commit()
            
            return result
        finally:
            session.close()
    
    def _test_by_service_type(self, connection: APIConnection) -> Dict[str, Any]:
        """Test connection based on service type."""
        
        if connection.service_type == ServiceType.AI_INFERENCE:
            return self._test_ai_connection(connection)
        elif connection.service_type == ServiceType.STREAMING:
            return self._test_streaming_connection(connection)
        elif connection.service_type == ServiceType.SOCIAL_MEDIA:
            return self._test_social_connection(connection)
        elif connection.service_type == ServiceType.STORAGE:
            return self._test_storage_connection(connection)
        else:
            return self._test_generic_connection(connection)
    
    def _test_ai_connection(self, connection: APIConnection) -> Dict[str, Any]:
        """Test AI inference API."""
        try:
            if connection.provider.lower() == 'anthropic':
                # Test Anthropic API
                from anthropic import Anthropic
                client = Anthropic(api_key=connection.api_key)
                
                response = client.messages.create(
                    model=connection.model_name or "claude-sonnet-4-20250514",
                    max_tokens=10,
                    messages=[{"role": "user", "content": "Hi"}]
                )
                
                return {
                    'status': 'success',
                    'message': 'Connection successful',
                    'details': {
                        'model': response.model,
                        'usage': response.usage.input_tokens + response.usage.output_tokens
                    }
                }
            
            elif connection.provider.lower() == 'openai':
                # Test OpenAI API
                import openai
                client = openai.OpenAI(api_key=connection.api_key)
                
                response = client.chat.completions.create(
                    model=connection.model_name or "gpt-4",
                    max_tokens=10,
                    messages=[{"role": "user", "content": "Hi"}]
                )
                
                return {
                    'status': 'success',
                    'message': 'Connection successful',
                    'details': {
                        'model': response.model,
                        'usage': response.usage.total_tokens
                    }
                }
            
            else:
                # Generic AI API test
                return self._test_generic_connection(connection)
        
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'Test failed: {str(e)}'
            }
    
    def _test_streaming_connection(self, connection: APIConnection) -> Dict[str, Any]:
        """Test streaming service API."""
        # Implement streaming service tests (Twitch, YouTube, etc.)
        return self._test_generic_connection(connection)
    
    def _test_social_connection(self, connection: APIConnection) -> Dict[str, Any]:
        """Test social media API."""
        # Implement social media tests (Twitter, Reddit, etc.)
        return self._test_generic_connection(connection)
    
    def _test_storage_connection(self, connection: APIConnection) -> Dict[str, Any]:
        """Test storage service API."""
        # Implement storage tests (S3, Drive, etc.)
        return self._test_generic_connection(connection)
    
    def _test_generic_connection(self, connection: APIConnection) -> Dict[str, Any]:
        """Generic API test using HTTP request."""
        if not connection.base_url:
            return {
                'status': 'pending',
                'message': 'No test endpoint configured'
            }
        
        try:
            headers = {}
            if connection.api_key:
                headers['Authorization'] = f'Bearer {connection.api_key}'
            
            response = self.session.get(
                connection.base_url,
                headers=headers,
                timeout=10
            )
            
            if response.status_code < 400:
                return {
                    'status': 'success',
                    'message': f'Connection successful (HTTP {response.status_code})'
                }
            else:
                return {
                    'status': 'failed',
                    'message': f'HTTP {response.status_code}: {response.text[:100]}'
                }
        
        except requests.exceptions.Timeout:
            return {
                'status': 'failed',
                'message': 'Connection timeout'
            }
        except requests.exceptions.ConnectionError:
            return {
                'status': 'failed',
                'message': 'Cannot connect to service'
            }
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'Test error: {str(e)}'
            }
    
    def update_connection(
        self,
        connection_id: int,
        name: str = None,
        description: str = None,
        api_key: str = None,
        base_url: str = None,
        model_name: str = None,
        config: Dict = None
    ) -> Optional[APIConnection]:
        """Update connection details."""
        session = db.get_session()
        try:
            connection = session.query(APIConnection).filter_by(id=connection_id).first()
            if not connection:
                return None
            
            if name is not None:
                connection.name = name
            if description is not None:
                connection.description = description
            if api_key is not None:
                connection.api_key = api_key
            if base_url is not None:
                connection.base_url = base_url
            if model_name is not None:
                connection.model_name = model_name
            if config is not None:
                connection.config = config
            
            session.commit()
            session.refresh(connection)
            
            print(f"✓ Updated API connection: {connection.name}")
            return connection
        finally:
            session.close()
    
    def delete_connection(self, connection_id: int) -> bool:
        """Delete an API connection."""
        session = db.get_session()
        try:
            connection = session.query(APIConnection).filter_by(id=connection_id).first()
            if not connection:
                return False
            
            name = connection.name
            session.delete(connection)
            session.commit()
            
            print(f"✓ Deleted API connection: {name}")
            return True
        finally:
            session.close()
    
    def track_usage(
        self,
        connection_id: int,
        tokens: int = 0,
        cost: float = 0.0
    ):
        """Track API usage for billing/analytics."""
        session = db.get_session()
        try:
            connection = session.query(APIConnection).filter_by(id=connection_id).first()
            if connection:
                connection.usage_count += 1
                connection.total_tokens += tokens
                connection.total_cost += cost
                connection.last_used = datetime.utcnow()
                session.commit()
        finally:
            session.close()
    
    def get_usage_stats(self, connection_id: int) -> Dict[str, Any]:
        """Get usage statistics for a connection."""
        session = db.get_session()
        try:
            connection = session.query(APIConnection).filter_by(id=connection_id).first()
            if not connection:
                return {}
            
            return {
                'usage_count': connection.usage_count,
                'total_tokens': connection.total_tokens,
                'total_cost': connection.total_cost,
                'last_used': connection.last_used.isoformat() if connection.last_used else None,
                'average_tokens_per_call': connection.total_tokens / max(connection.usage_count, 1)
            }
        finally:
            session.close()
