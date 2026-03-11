"""
Enhanced security module for the sandbox system.

This module provides:
- Advanced command filtering with regex patterns
- File system access controls
- Network security measures
- Input validation and sanitization
- Security audit logging
"""

import re
import os
import sys
import logging
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import tempfile
import shutil
import socket

logger = logging.getLogger(__name__)

class SecurityLevel(Enum):
    """Security levels for different operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class SecurityViolation:
    """Represents a security violation."""
    level: SecurityLevel
    type: str
    message: str
    input_data: str
    timestamp: float
    remediation: Optional[str] = None

class CommandFilter:
    """Advanced command filtering with regex patterns."""
    
    def __init__(self):
        self.dangerous_patterns = {
            SecurityLevel.CRITICAL: [
                r'rm\s+-rf\s+/',  # Delete root
                r':\(\)\{\s*:\|\:&\s*\}',  # Fork bomb
                r'sudo\s+rm\s+-rf',  # Sudo delete
                r'mkfs\s+',  # Format filesystem
                r'dd\s+if=.*of=/dev/',  # Direct disk write
                r'curl\s+.*\|\s*bash',  # Remote code execution
                r'wget\s+.*\|\s*sh',  # Remote code execution
                r'eval\s+\$\(',  # Command injection
                r'system\s*\(',  # System calls
                r'exec\s*\(',  # Execute calls
                r'popen\s*\(',  # Process open
                r'subprocess\s*\.',  # Subprocess calls
            ],
            SecurityLevel.HIGH: [
                r'chmod\s+777',  # Dangerous permissions
                r'chown\s+-R',  # Recursive ownership change
                r'passwd\s+',  # Password change
                r'userdel\s+',  # User deletion
                r'useradd\s+',  # User addition
                r'groupdel\s+',  # Group deletion
                r'mount\s+',  # Mount operations
                r'umount\s+',  # Unmount operations
                r'fdisk\s+',  # Disk partitioning
                r'parted\s+',  # Disk partitioning
                r'iptables\s+',  # Firewall rules
                r'firewall-cmd\s+',  # Firewall management
                r'netstat\s+',  # Network statistics
                r'ss\s+',  # Socket statistics
                r'lsof\s+',  # List open files
            ],
            SecurityLevel.MEDIUM: [
                r'systemctl\s+',  # System control
                r'service\s+',  # Service management
                r'shutdown\s+',  # System shutdown
                r'reboot\s+',  # System reboot
                r'halt\s+',  # System halt
                r'poweroff\s+',  # System poweroff
                r'init\s+',  # Init system
                r'killall\s+',  # Kill all processes
                r'pkill\s+',  # Process kill
                r'kill\s+-9',  # Force kill
                r'crontab\s+',  # Cron scheduling
                r'at\s+',  # Job scheduling
                r'nohup\s+',  # Background processes
            ],
            SecurityLevel.LOW: [
                r'history\s+',  # Command history
                r'alias\s+',  # Command aliases
                r'export\s+',  # Environment variables
                r'unset\s+',  # Unset variables
                r'source\s+',  # Source files
                r'\.\s+',  # Dot command
                r'bash\s+',  # Bash execution
                r'sh\s+',  # Shell execution
                r'python\s+.*-c',  # Python execution
                r'perl\s+.*-e',  # Perl execution
                r'ruby\s+.*-e',  # Ruby execution
            ]
        }
        
        # Network-related patterns
        self.network_patterns = [
            r'nc\s+',  # Netcat
            r'telnet\s+',  # Telnet
            r'ssh\s+',  # SSH
            r'scp\s+',  # SCP
            r'rsync\s+',  # Rsync
            r'ftp\s+',  # FTP
            r'sftp\s+',  # SFTP
            r'wget\s+',  # Wget
            r'curl\s+',  # Curl
            r'ping\s+',  # Ping
            r'traceroute\s+',  # Traceroute
            r'nmap\s+',  # Network mapper
            r'dig\s+',  # DNS lookup
            r'host\s+',  # Host lookup
            r'nslookup\s+',  # DNS lookup
        ]
        
        # File system patterns
        self.filesystem_patterns = [
            r'/etc/passwd',  # System users
            r'/etc/shadow',  # System passwords
            r'/etc/sudoers',  # Sudo configuration
            r'/etc/hosts',  # Host configuration
            r'/etc/fstab',  # File system table
            r'/boot/',  # Boot directory
            r'/sys/',  # System directory
            r'/proc/',  # Process directory
            r'/dev/',  # Device directory
            r'~/.ssh/',  # SSH keys
            r'~/.bashrc',  # Bash configuration
            r'~/.profile',  # Profile configuration
        ]
    
    def check_command(self, command: str) -> Tuple[bool, Optional[SecurityViolation]]:
        """
        Check if a command is safe to execute.
        
        Args:
            command: The command to check
            
        Returns:
            Tuple of (is_safe, violation_info)
        """
        command_lower = command.lower().strip()
        
        # Check against all security levels
        for level, patterns in self.dangerous_patterns.items():
            for pattern in patterns:
                if re.search(pattern, command_lower, re.IGNORECASE):
                    violation = SecurityViolation(
                        level=level,
                        type="dangerous_command",
                        message=f"Command contains dangerous pattern: {pattern}",
                        input_data=command,
                        timestamp=time.time(),
                        remediation=f"Remove or modify the pattern: {pattern}"
                    )
                    return False, violation
        
        # Check network patterns if network access is restricted
        for pattern in self.network_patterns:
            if re.search(pattern, command_lower, re.IGNORECASE):
                violation = SecurityViolation(
                    level=SecurityLevel.MEDIUM,
                    type="network_command",
                    message=f"Command contains network pattern: {pattern}",
                    input_data=command,
                    timestamp=time.time(),
                    remediation="Network access may be restricted"
                )
                return False, violation
        
        # Check file system patterns
        for pattern in self.filesystem_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                violation = SecurityViolation(
                    level=SecurityLevel.HIGH,
                    type="filesystem_access",
                    message=f"Command accesses sensitive path: {pattern}",
                    input_data=command,
                    timestamp=time.time(),
                    remediation="Access to sensitive paths is restricted"
                )
                return False, violation
        
        return True, None

class FileSystemSecurity:
    """File system access controls and sandboxing."""
    
    def __init__(self, allowed_paths: Optional[List[str]] = None):
        self.allowed_paths = set(allowed_paths or [])
        self.restricted_paths = {
            '/etc', '/boot', '/sys', '/proc', '/dev',
            '/root', '/var/log', '/var/run', '/tmp/systemd-private'
        }
        self.temp_dirs = set()
        
    def is_path_allowed(self, path: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a path is allowed for access.

        Security S4: Uses is_relative_to() instead of startswith() to prevent
        path traversal via symlinks and similar-prefix attacks.

        Args:
            path: The path to check

        Returns:
            Tuple of (is_allowed, reason)
        """
        try:
            resolved_path = Path(path).resolve()

            # Check if path is explicitly allowed
            # Security S4: When allowed_paths is configured, only allow paths within them
            if self.allowed_paths:
                for allowed in self.allowed_paths:
                    allowed_path = Path(allowed).resolve()
                    if resolved_path.is_relative_to(allowed_path):
                        # Path is allowed, now check if it's also restricted
                        break
                else:
                    # No allowed path matched, deny by default
                    return False, f"Path '{path}' is not within allowed paths"

            # Check if path is restricted
            for restricted in self.restricted_paths:
                restricted_path = Path(restricted).resolve()
                if resolved_path.is_relative_to(restricted_path):
                    return False, f"Path '{path}' is in restricted area: {restricted}"
            
            # Check for dangerous file extensions
            dangerous_extensions = {'.so', '.dll', '.exe', '.bat', '.cmd', '.scr'}
            if resolved_path.suffix.lower() in dangerous_extensions:
                return False, f"File extension '{resolved_path.suffix}' is not allowed"
            
            return True, None
            
        except Exception as e:
            return False, f"Error resolving path: {str(e)}"
    
    def create_sandbox_directory(self, base_name: str = "sandbox") -> str:
        """
        Create a temporary sandbox directory.
        
        Args:
            base_name: Base name for the directory
            
        Returns:
            Path to the created directory
        """
        temp_dir = tempfile.mkdtemp(prefix=f"{base_name}_")
        self.temp_dirs.add(temp_dir)
        self.allowed_paths.add(temp_dir)
        return temp_dir
    
    def cleanup_sandbox_directories(self):
        """Clean up all sandbox directories."""
        for temp_dir in self.temp_dirs.copy():
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                self.temp_dirs.remove(temp_dir)
                self.allowed_paths.discard(temp_dir)
            except Exception as e:
                logger.error(f"Error cleaning up sandbox directory {temp_dir}: {e}")

class NetworkSecurity:
    """Network security controls."""
    
    def __init__(self):
        self.allowed_ports = {80, 443, 8000, 8080, 8443, 8765}  # Common web ports
        self.blocked_ports = {22, 23, 25, 53, 110, 143, 993, 995}  # System ports
        self.port_assignments = {}  # Track port assignments
        
    def is_port_allowed(self, port: int) -> Tuple[bool, Optional[str]]:
        """
        Check if a port is allowed for use.
        
        Args:
            port: The port number to check
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        if port in self.blocked_ports:
            return False, f"Port {port} is blocked (system port)"
        
        if port < 1024:
            return False, f"Port {port} is privileged (< 1024)"
        
        if port > 65535:
            return False, f"Port {port} is invalid (> 65535)"
        
        return True, None
    
    def allocate_port(self, preferred_port: Optional[int] = None) -> Optional[int]:
        """
        Allocate a port for use.
        
        Args:
            preferred_port: Preferred port number
            
        Returns:
            Allocated port number or None if allocation failed
        """
        if preferred_port:
            is_allowed, reason = self.is_port_allowed(preferred_port)
            if not is_allowed:
                logger.warning(f"Port {preferred_port} not allowed: {reason}")
                return None
            
            if self._is_port_available(preferred_port):
                self.port_assignments[preferred_port] = time.time()
                return preferred_port
        
        # Find available port in allowed range
        for port in range(8000, 9000):
            is_allowed, _ = self.is_port_allowed(port)
            if is_allowed and self._is_port_available(port):
                self.port_assignments[port] = time.time()
                return port
        
        return None
    
    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return True
        except OSError:
            return False
    
    def release_port(self, port: int):
        """Release a port allocation."""
        self.port_assignments.pop(port, None)

class InputValidator:
    """Input validation and sanitization."""
    
    def __init__(self):
        self.max_input_length = 10000  # Maximum input length
        self.suspicious_patterns = [
            r'<script',  # XSS attempts
            r'javascript:',  # JavaScript URLs
            r'data:',  # Data URLs
            r'vbscript:',  # VBScript URLs
            r'onload=',  # Event handlers
            r'onclick=',  # Event handlers
            r'onerror=',  # Event handlers
            r'\\x',  # Hex encoding
            r'\\u',  # Unicode encoding
            r'%3C',  # URL encoded <
            r'%3E',  # URL encoded >
            r'&lt;',  # HTML encoded <
            r'&gt;',  # HTML encoded >
        ]
    
    def validate_input(self, input_data: str, input_type: str = "general") -> Tuple[bool, Optional[str]]:
        """
        Validate input data.
        
        Args:
            input_data: The input to validate
            input_type: Type of input (code, command, text, etc.)
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Check length
        if len(input_data) > self.max_input_length:
            return False, f"Input too long: {len(input_data)} > {self.max_input_length}"
        
        # Check for suspicious patterns
        for pattern in self.suspicious_patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                return False, f"Input contains suspicious pattern: {pattern}"
        
        # Additional validation based on input type
        if input_type == "code":
            return self._validate_code(input_data)
        elif input_type == "command":
            return self._validate_command(input_data)
        elif input_type == "filename":
            return self._validate_filename(input_data)
        
        return True, None
    
    def _validate_code(self, code: str) -> Tuple[bool, Optional[str]]:
        """Validate code input."""
        dangerous_imports = [
            'subprocess', 'os.system', 'eval', 'exec',
            'importlib', '__import__', 'globals', 'locals',
            'compile', 'open', 'file', 'input', 'raw_input'
        ]
        
        for dangerous in dangerous_imports:
            if dangerous in code:
                return False, f"Code contains dangerous import/call: {dangerous}"
        
        return True, None
    
    def _validate_command(self, command: str) -> Tuple[bool, Optional[str]]:
        """Validate command input."""
        # Check for command injection patterns
        injection_patterns = [
            r';.*rm', r'&&.*rm', r'\|\|.*rm',
            r';.*curl', r'&&.*curl', r'\|\|.*curl',
            r';.*wget', r'&&.*wget', r'\|\|.*wget',
            r'`.*`', r'\$\(.*\)', r'\$\{.*\}'
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"Command contains injection pattern: {pattern}"
        
        return True, None
    
    def _validate_filename(self, filename: str) -> Tuple[bool, Optional[str]]:
        """Validate filename input."""
        # Check for path traversal
        if '..' in filename or filename.startswith('/'):
            return False, "Filename contains path traversal"
        
        # Check for dangerous characters
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\x00']
        for char in dangerous_chars:
            if char in filename:
                return False, f"Filename contains dangerous character: {char}"
        
        return True, None

class SecurityAuditor:
    """Security audit logging and monitoring."""
    
    def __init__(self):
        self.violations = []
        self.max_violations = 1000
        self.audit_log = []
        
    def log_violation(self, violation: SecurityViolation):
        """Log a security violation."""
        self.violations.append(violation)
        
        # Keep only recent violations
        if len(self.violations) > self.max_violations:
            self.violations = self.violations[-self.max_violations:]
        
        # Log to system logger
        logger.warning(f"Security violation: {violation.type} - {violation.message}")
        
        # Store in audit log
        self.audit_log.append({
            'timestamp': violation.timestamp,
            'level': violation.level.value,
            'type': violation.type,
            'message': violation.message,
            'input_hash': hashlib.sha256(violation.input_data.encode()).hexdigest()[:16]
        })
    
    def get_violations(self, level: Optional[SecurityLevel] = None, 
                      since: Optional[float] = None) -> List[SecurityViolation]:
        """Get security violations."""
        violations = self.violations
        
        if level:
            violations = [v for v in violations if v.level == level]
        
        if since:
            violations = [v for v in violations if v.timestamp >= since]
        
        return violations
    
    def get_security_summary(self) -> Dict[str, Any]:
        """Get security summary statistics."""
        if not self.violations:
            return {
                'total_violations': 0,
                'violations_by_level': {},
                'violations_by_type': {},
                'recent_violations': 0
            }
        
        recent_time = time.time() - 3600  # Last hour
        recent_violations = [v for v in self.violations if v.timestamp >= recent_time]
        
        violations_by_level = {}
        violations_by_type = {}
        
        for v in self.violations:
            level = v.level.value
            violations_by_level[level] = violations_by_level.get(level, 0) + 1
            violations_by_type[v.type] = violations_by_type.get(v.type, 0) + 1
        
        return {
            'total_violations': len(self.violations),
            'violations_by_level': violations_by_level,
            'violations_by_type': violations_by_type,
            'recent_violations': len(recent_violations)
        }

class SecurityManager:
    """Main security manager coordinating all security components."""
    
    def __init__(self, security_level: SecurityLevel = SecurityLevel.MEDIUM):
        self.security_level = security_level
        self.command_filter = CommandFilter()
        self.filesystem_security = FileSystemSecurity()
        self.network_security = NetworkSecurity()
        self.input_validator = InputValidator()
        self.auditor = SecurityAuditor()
        
        logger.info(f"Security manager initialized with level: {security_level.value}")
    
    def check_command_security(self, command: str) -> Tuple[bool, Optional[SecurityViolation]]:
        """Check if a command is safe to execute."""
        # Validate input
        is_valid, reason = self.input_validator.validate_input(command, "command")
        if not is_valid:
            violation = SecurityViolation(
                level=SecurityLevel.HIGH,
                type="input_validation",
                message=f"Command failed validation: {reason}",
                input_data=command,
                timestamp=time.time()
            )
            self.auditor.log_violation(violation)
            return False, violation
        
        # Check command patterns
        is_safe, violation = self.command_filter.check_command(command)
        
        # Log violation if found
        if not is_safe and violation:
            self.auditor.log_violation(violation)
        
        return is_safe, violation
    
    def check_path_security(self, path: str) -> Tuple[bool, Optional[str]]:
        """Check if a path is safe to access."""
        return self.filesystem_security.is_path_allowed(path)
    
    def allocate_secure_port(self, preferred_port: Optional[int] = None) -> Optional[int]:
        """Allocate a secure port."""
        return self.network_security.allocate_port(preferred_port)
    
    def create_secure_workspace(self) -> str:
        """Create a secure workspace directory."""
        return self.filesystem_security.create_sandbox_directory()
    
    def cleanup_security_resources(self):
        """Clean up security-related resources."""
        self.filesystem_security.cleanup_sandbox_directories()
    
    def get_security_status(self) -> Dict[str, Any]:
        """Get comprehensive security status."""
        return {
            'security_level': self.security_level.value,
            'audit_summary': self.auditor.get_security_summary(),
            'active_ports': len(self.network_security.port_assignments),
            'sandbox_directories': len(self.filesystem_security.temp_dirs),
            'allowed_paths': len(self.filesystem_security.allowed_paths)
        }

# Global security manager instance
_security_manager = None

def get_security_manager(level: SecurityLevel = SecurityLevel.MEDIUM) -> SecurityManager:
    """Get the global security manager instance."""
    global _security_manager
    if _security_manager is None or _security_manager.security_level != level:
        _security_manager = SecurityManager(level)
    return _security_manager
