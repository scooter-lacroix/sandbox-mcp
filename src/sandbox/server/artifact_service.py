"""
Server Artifact Service for Sandbox MCP.

This module handles artifact listing and management for the server,
replacing duplicate logic from the stdio server.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class ServerArtifactService:
    """
    Service for managing server artifacts.
    
    This service provides unified artifact listing, categorization,
    and retrieval, replacing duplicate logic in the stdio server.
    """
    
    # File type categories
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp', '.tiff'}
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'}
    DATA_EXTENSIONS = {'.csv', '.json', '.xml', '.yaml', '.yml', '.parquet', '.pkl', '.pickle'}
    CODE_EXTENSIONS = {'.py', '.js', '.html', '.css', '.sql', '.sh', '.bat'}
    DOCUMENT_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.md', '.rtf'}
    AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}
    
    def __init__(self):
        """Initialize the server artifact service."""
        pass
    
    def _categorize_file(self, file_path: Path) -> str:
        """
        Categorize a file based on its extension and path.
        
        Args:
            file_path: Path to the file.
        
        Returns:
            Category string.
        """
        suffix = file_path.suffix.lower()
        path_str = str(file_path).lower()
        
        # Check for Manim files
        if any(pattern in path_str for pattern in ['manim', 'media', 'videos', 'images']):
            return 'manim'
        
        # Extension-based categorization
        if suffix in self.IMAGE_EXTENSIONS:
            return 'images'
        elif suffix in self.VIDEO_EXTENSIONS:
            return 'videos'
        elif suffix in self.DATA_EXTENSIONS:
            return 'data'
        elif suffix in self.CODE_EXTENSIONS:
            return 'code'
        elif suffix in self.DOCUMENT_EXTENSIONS:
            return 'documents'
        elif suffix in self.AUDIO_EXTENSIONS:
            return 'audio'
        else:
            return 'other'
    
    async def list_artifacts(
        self,
        directory: Path,
        recursive: bool = True,
        category_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List artifacts in a directory.
        
        Args:
            directory: The directory to scan.
            recursive: Whether to scan subdirectories recursively.
            category_filter: Optional category to filter by.
        
        Returns:
            List of artifact dictionaries.
        """
        artifacts = []
        
        if not directory.exists():
            logger.warning(f"Directory does not exist: {directory}")
            return artifacts
        
        pattern = "**/*" if recursive else "*"
        
        for file_path in directory.glob(pattern):
            if file_path.is_file():
                try:
                    stat = file_path.stat()
                    category = self._categorize_file(file_path)
                    
                    # Apply category filter if specified
                    if category_filter and category != category_filter:
                        continue
                    
                    artifact_info = {
                        'name': file_path.name,
                        'path': str(file_path.relative_to(directory)),
                        'full_path': str(file_path),
                        'size': stat.st_size,
                        'created': stat.st_ctime,
                        'modified': stat.st_mtime,
                        'extension': suffix if (suffix := file_path.suffix.lower()) else '',
                        'category': category,
                    }
                    artifacts.append(artifact_info)
                except Exception as e:
                    logger.warning(f"Failed to get info for {file_path}: {e}")
        
        return artifacts
    
    async def get_artifact(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific artifact.
        
        Args:
            file_path: Path to the artifact.
        
        Returns:
            Artifact information dictionary, or None if not found.
        """
        if not file_path.exists() or not file_path.is_file():
            return None
        
        try:
            stat = file_path.stat()
            category = self._categorize_file(file_path)
            
            return {
                'name': file_path.name,
                'path': str(file_path),
                'size': stat.st_size,
                'created': stat.st_ctime,
                'modified': stat.st_mtime,
                'extension': file_path.suffix.lower(),
                'category': category,
            }
        except Exception as e:
            logger.error(f"Failed to get artifact info for {file_path}: {e}")
            return None
    
    async def get_artifact_summary(self, directory: Path) -> Dict[str, Any]:
        """
        Get a summary of artifacts in a directory.
        
        Args:
            directory: The directory to summarize.
        
        Returns:
            Summary dictionary with counts and totals.
        """
        artifacts = await self.list_artifacts(directory)
        
        summary = {
            'total_count': len(artifacts),
            'total_size': sum(a['size'] for a in artifacts),
            'by_category': {},
        }
        
        for artifact in artifacts:
            category = artifact['category']
            if category not in summary['by_category']:
                summary['by_category'][category] = {
                    'count': 0,
                    'total_size': 0,
                }
            summary['by_category'][category]['count'] += 1
            summary['by_category'][category]['total_size'] += artifact['size']
        
        return summary


# Singleton instance for convenience
_server_artifact_service: Optional[ServerArtifactService] = None


def get_server_artifact_service() -> ServerArtifactService:
    """
    Get the global server artifact service instance.
    
    Returns:
        The singleton ServerArtifactService instance.
    """
    global _server_artifact_service
    if _server_artifact_service is None:
        _server_artifact_service = ServerArtifactService()
    return _server_artifact_service
