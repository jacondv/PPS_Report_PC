# report/templates/base_template.py

from abc import ABC, abstractmethod

class BaseReportTemplate(ABC):

    @abstractmethod
    def build(self, story, context):
        """Build full report layout"""
        pass