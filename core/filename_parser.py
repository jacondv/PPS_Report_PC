"""
Parse project information from PLY filename.
Format: projectname#jobnumber#hhmmss#name.ply
"""

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ProjectInfo:
    """Project information extracted from filename."""
    project_name: str
    job_number: str
    scan_time: str
    segment_name: str
    original_filename: str
    parse_success: bool = True
    
    @property
    def formatted_time(self) -> str:
        """Format time as HH:MM:SS."""
        if len(self.scan_time) == 6:
            return f"{self.scan_time[:2]}:{self.scan_time[2:4]}:{self.scan_time[4:6]}"
        return self.scan_time
    
    @property
    def report_date(self) -> str:
        """Get current date for report."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_filename(filepath: str) -> ProjectInfo:
    """
    Parse PLY filename to extract project information.
    
    Expected format: projectname#jobnumber#hhmmss#name.ply
    
    Args:
        filepath: Full path to the PLY file
        
    Returns:
        ProjectInfo dataclass with extracted information
    """
    filename = os.path.basename(filepath)
    name_without_ext = os.path.splitext(filename)[0]
    
    # Try to parse with # delimiter
    parts = name_without_ext.split('#')
    
    if len(parts) >= 4:
        return ProjectInfo(
            project_name=parts[0],
            job_number=parts[1],
            scan_time=parts[2],
            segment_name='#'.join(parts[3:]),  # Join remaining parts
            original_filename=filename,
            parse_success=True
        )
    elif len(parts) == 3:
        return ProjectInfo(
            project_name=parts[0],
            job_number=parts[1],
            scan_time=parts[2],
            segment_name="",
            original_filename=filename,
            parse_success=True
        )
    else:
        # Fallback: use filename as project name
        return ProjectInfo(
            project_name=name_without_ext,
            job_number="N/A",
            scan_time="N/A",
            segment_name="",
            original_filename=filename,
            parse_success=False
        )


def validate_time_format(time_str: str) -> bool:
    """Validate if time string is in HHMMSS format."""
    if len(time_str) != 6:
        return False
    try:
        hour = int(time_str[:2])
        minute = int(time_str[2:4])
        second = int(time_str[4:6])
        return 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59
    except ValueError:
        return False
