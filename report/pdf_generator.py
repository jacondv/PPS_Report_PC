"""
PDF Report Generator for Tunnel Concrete Thickness Analysis.
"""

import os
import io
from datetime import datetime
from typing import Optional

import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, 
    Image, PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.filename_parser import ProjectInfo
from core.calculator import CalculationResult, ThicknessDistribution


class PDFReportGenerator:
    """Generate PDF reports for tunnel analysis."""
    
    def __init__(self, output_path: str):
        self.output_path = output_path
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='Title_Custom',
            parent=self.styles['Title'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#1a365d'),
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='Heading_Custom',
            parent=self.styles['Heading1'],
            fontSize=14,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor('#2c5282'),
            borderPadding=5,
            borderColor=colors.HexColor('#e2e8f0'),
            borderWidth=0,
            backColor=colors.HexColor('#f7fafc')
        ))
        
        self.styles.add(ParagraphStyle(
            name='Info_Label',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#718096'),
        ))
        
        self.styles.add(ParagraphStyle(
            name='Info_Value',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#1a202c'),
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#a0aec0'),
            alignment=TA_CENTER
        ))
    
    def generate_report(self,
                       project_info: ProjectInfo,
                       calculation_result: CalculationResult,
                       thickness_distribution: ThicknessDistribution,
                       target_thickness_min: float,
                       target_thickness_max: float,
                       screenshot_path: Optional[str] = None) -> str:
        """
        Generate the PDF report.
        
        Args:
            project_info: Project information from filename
            calculation_result: Calculation results (area, volume, etc.)
            thickness_distribution: Thickness distribution data
            target_thickness_min: Target minimum thickness (mm)
            target_thickness_max: Target maximum thickness (mm)
            screenshot_path: Optional path to 3D screenshot
            
        Returns:
            Path to generated PDF file
        """
        doc = SimpleDocTemplate(
            self.output_path,
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )
        
        story = []
        
        # Title
        story.append(Paragraph(
            "BÁO CÁO PHÂN TÍCH ĐỘ DÀY BÊ TÔNG PHUN",
            self.styles['Title_Custom']
        ))
        story.append(Paragraph(
            "Tunnel Shotcrete Thickness Analysis Report",
            self.styles['Normal']
        ))
        story.append(Spacer(1, 20))
        
        # Horizontal line
        story.append(HRFlowable(
            width="100%", thickness=2, 
            color=colors.HexColor('#3182ce'),
            spaceBefore=10, spaceAfter=20
        ))
        
        # Project Information Section
        story.append(Paragraph("1. THÔNG TIN DỰ ÁN", self.styles['Heading_Custom']))
        
        info_data = [
            ["Tên dự án (Project):", project_info.project_name],
            ["Mã công việc (Job Number):", project_info.job_number],
            ["Thời gian scan:", project_info.formatted_time],
            ["Tên segment:", project_info.segment_name or "N/A"],
            ["File gốc:", project_info.original_filename],
            ["Ngày tạo báo cáo:", project_info.report_date],
        ]
        
        info_table = Table(info_data, colWidths=[150, 300])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#4a5568')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#1a202c')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7fafc')),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 20))
        
        # Results Section
        story.append(Paragraph("2. KẾT QUẢ PHÂN TÍCH", self.styles['Heading_Custom']))
        
        results_data = [
            ["Chỉ tiêu", "Giá trị", "Đơn vị"],
            ["Diện tích vùng đã phun", f"{calculation_result.surface_area_m2:.4f}", "m²"],
            ["Thể tích bê tông đã phun", f"{calculation_result.volume_m3:.6f}", "m³"],
            ["Thể tích bê tông (lít)", f"{calculation_result.volume_liters:.2f}", "lít"],
            ["Độ dày trung bình", f"{calculation_result.mean_thickness_mm:.2f}", "mm"],
            ["Độ dày nhỏ nhất", f"{calculation_result.min_thickness_mm:.2f}", "mm"],
            ["Độ dày lớn nhất", f"{calculation_result.max_thickness_mm:.2f}", "mm"],
            ["Độ lệch chuẩn", f"{calculation_result.std_thickness_mm:.2f}", "mm"],
            ["Số điểm phân tích", f"{calculation_result.num_points:,}", "điểm"],
        ]
        
        results_table = Table(results_data, colWidths=[200, 150, 100])
        results_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3182ce')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Body
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            
            # Alternating row colors
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#ebf8ff')),
            ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#ebf8ff')),
            ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor('#ebf8ff')),
            ('BACKGROUND', (0, 7), (-1, 7), colors.HexColor('#ebf8ff')),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bee3f8')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(results_table)
        story.append(Spacer(1, 20))
        
        # Target thickness info
        story.append(Paragraph("3. PHÂN BỐ ĐỘ DÀY", self.styles['Heading_Custom']))
        
        target_info = f"""
        <b>Độ dày mong muốn:</b> {target_thickness_min:.1f} mm - {target_thickness_max:.1f} mm
        """
        story.append(Paragraph(target_info, self.styles['Normal']))
        story.append(Spacer(1, 10))
        
        # Distribution summary
        dist_data = [
            ["Phân loại", "Số điểm", "Tỷ lệ (%)"],
            [f"Dưới tiêu chuẩn (< {target_thickness_min:.1f} mm)", 
             f"{thickness_distribution.below_target:,}",
             f"{thickness_distribution.below_target_percent:.1f}%"],
            [f"Đạt tiêu chuẩn ({target_thickness_min:.1f} - {target_thickness_max:.1f} mm)",
             f"{thickness_distribution.within_target:,}",
             f"{thickness_distribution.within_target_percent:.1f}%"],
            [f"Vượt tiêu chuẩn (> {target_thickness_max:.1f} mm)",
             f"{thickness_distribution.above_target:,}",
             f"{thickness_distribution.above_target_percent:.1f}%"],
        ]
        
        dist_table = Table(dist_data, colWidths=[250, 100, 100])
        dist_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d3748')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Below target - red
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#fed7d7')),
            ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#c53030')),
            
            # Within target - green
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#c6f6d5')),
            ('TEXTCOLOR', (0, 2), (-1, 2), colors.HexColor('#276749')),
            
            # Above target - yellow
            ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#fefcbf')),
            ('TEXTCOLOR', (0, 3), (-1, 3), colors.HexColor('#975a16')),
            
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#a0aec0')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(dist_table)
        story.append(Spacer(1, 20))
        
        # Generate and add histogram
        histogram_path = self._generate_histogram(
            thickness_distribution, 
            target_thickness_min, 
            target_thickness_max
        )
        if histogram_path:
            story.append(Paragraph("4. BIỂU ĐỒ PHÂN BỐ ĐỘ DÀY", self.styles['Heading_Custom']))
            img = Image(histogram_path, width=450, height=300)
            story.append(img)
            story.append(Spacer(1, 10))
        
        # Add 3D screenshot if available
        if screenshot_path and os.path.exists(screenshot_path):
            story.append(PageBreak())
            story.append(Paragraph("5. HÌNH ẢNH 3D", self.styles['Heading_Custom']))
            img = Image(screenshot_path, width=450, height=350)
            story.append(img)
        
        # Footer
        story.append(Spacer(1, 30))
        story.append(HRFlowable(
            width="100%", thickness=1,
            color=colors.HexColor('#e2e8f0'),
            spaceBefore=20, spaceAfter=10
        ))
        story.append(Paragraph(
            f"Báo cáo được tạo tự động bởi Tunnel Analyzer | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            self.styles['Footer']
        ))
        
        # Build PDF
        doc.build(story)
        
        # Clean up histogram temp file
        if histogram_path and os.path.exists(histogram_path):
            try:
                os.remove(histogram_path)
            except:
                pass
        
        return self.output_path
    
    def _generate_histogram(self, 
                           distribution: ThicknessDistribution,
                           target_min: float,
                           target_max: float) -> Optional[str]:
        """Generate histogram image and return path."""
        if len(distribution.histogram_bins) == 0:
            return None
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Calculate bin centers
        bin_centers = (distribution.histogram_bins[:-1] + distribution.histogram_bins[1:]) / 2
        bin_width = distribution.histogram_bins[1] - distribution.histogram_bins[0]
        
        # Color bars based on target range
        bar_colors = []
        for center in bin_centers:
            if center < target_min:
                bar_colors.append('#fc8181')  # Red - below
            elif center > target_max:
                bar_colors.append('#f6e05e')  # Yellow - above
            else:
                bar_colors.append('#68d391')  # Green - within
        
        # Create histogram
        bars = ax.bar(bin_centers, distribution.histogram_counts, 
                     width=bin_width * 0.9, color=bar_colors, 
                     edgecolor='white', linewidth=0.5)
        
        # Add target range shading
        ax.axvspan(target_min, target_max, alpha=0.2, color='green', 
                  label=f'Khoảng mong muốn ({target_min:.1f}-{target_max:.1f} mm)')
        
        # Add vertical lines for target boundaries
        ax.axvline(x=target_min, color='#c53030', linestyle='--', linewidth=2,
                  label=f'Giới hạn dưới ({target_min:.1f} mm)')
        ax.axvline(x=target_max, color='#c53030', linestyle='--', linewidth=2,
                  label=f'Giới hạn trên ({target_max:.1f} mm)')
        
        # Labels and title
        ax.set_xlabel('Độ dày (mm)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Số điểm', fontsize=12, fontweight='bold')
        ax.set_title('Phân bố độ dày bê tông phun\nThickness Distribution', 
                    fontsize=14, fontweight='bold', pad=20)
        
        # Legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#fc8181', label=f'Dưới tiêu chuẩn ({distribution.below_target_percent:.1f}%)'),
            Patch(facecolor='#68d391', label=f'Đạt tiêu chuẩn ({distribution.within_target_percent:.1f}%)'),
            Patch(facecolor='#f6e05e', label=f'Vượt tiêu chuẩn ({distribution.above_target_percent:.1f}%)'),
        ]
        ax.legend(handles=legend_elements, loc='upper right', fontsize=10)
        
        # Grid
        ax.grid(True, axis='y', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)
        
        # Style
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        plt.tight_layout()
        
        # Save to temp file
        import tempfile
        temp_path = os.path.join(tempfile.gettempdir(), 'histogram_temp.png')
        plt.savefig(temp_path, dpi=150, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        plt.close(fig)
        
        return temp_path


def generate_report(output_path: str,
                   project_info: ProjectInfo,
                   calculation_result: CalculationResult,
                   thickness_distribution: ThicknessDistribution,
                   target_thickness_min: float,
                   target_thickness_max: float,
                   screenshot_path: Optional[str] = None) -> str:
    """
    Convenience function to generate a PDF report.
    
    Returns:
        Path to generated PDF file
    """
    generator = PDFReportGenerator(output_path)
    return generator.generate_report(
        project_info=project_info,
        calculation_result=calculation_result,
        thickness_distribution=thickness_distribution,
        target_thickness_min=target_thickness_min,
        target_thickness_max=target_thickness_max,
        screenshot_path=screenshot_path
    )
