"""
Generate comprehensive PDF documentation for ML Filesystem v1.8+
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib import colors
from datetime import datetime
import os

def create_comprehensive_pdf():
    """Create the complete documentation PDF"""
    
    # Create PDF
    pdf_file = "ML_Filesystem_v18_Complete_Documentation.pdf"
    doc = SimpleDocTemplate(
        pdf_file,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=1*inch,
        bottomMargin=0.75*inch
    )
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading1_style = ParagraphStyle(
        'CustomHeading1',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    heading2_style = ParagraphStyle(
        'CustomHeading2',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=10,
        spaceBefore=10,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=10
    )
    
    code_style = ParagraphStyle(
        'Code',
        parent=styles['Code'],
        fontSize=9,
        fontName='Courier',
        leftIndent=20,
        spaceAfter=10,
        textColor=colors.HexColor('#c7254e'),
        backColor=colors.HexColor('#f9f2f4')
    )
    
    # Build content
    story = []
    
    # Cover Page
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph("ML Filesystem v1.8+", title_style))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("Complete Technical Documentation", heading1_style))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("Package Version 1.0", body_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", body_style))
    story.append(Spacer(1, 1*inch))
    
    # Stats table
    stats_data = [
        ['Documentation', '173,000+ words'],
        ['Source Code', '~20,000 lines'],
        ['Python Modules', '24 files'],
        ['API Endpoints', '50+'],
        ['Database Tables', '17'],
        ['Features', '8 major enhancements'],
    ]
    
    stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    
    story.append(stats_table)
    story.append(PageBreak())
    
    # Table of Contents
    story.append(Paragraph("Table of Contents", heading1_style))
    story.append(Spacer(1, 0.2*inch))
    
    toc_items = [
        "1. Package Overview",
        "2. Quick Start Guide (30 Minutes)",
        "3. System Architecture",
        "4. Complete Component Inventory",
        "5. API Reference",
        "6. Database Schema",
        "7. Feature Documentation",
        "8. Integration Guide",
        "9. Troubleshooting",
        "10. Extension Points",
        "Appendix A: Configuration Reference",
        "Appendix B: Code Inventory",
        "Appendix C: Dependency Map",
    ]
    
    for item in toc_items:
        story.append(Paragraph(item, body_style))
    
    story.append(PageBreak())
    
    # Section 1: Package Overview
    story.append(Paragraph("1. Package Overview", heading1_style))
    story.append(Paragraph(
        "The ML Filesystem v1.8+ is a sophisticated AI-native file management system "
        "that integrates machine learning capabilities directly into file operations. "
        "This documentation package provides everything needed to understand, build, "
        "deploy, and extend the system.",
        body_style
    ))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Key Features", heading2_style))
    features = [
        "<b>Training Blocks:</b> First-class data collections with toggle enable/disable",
        "<b>Enhanced Agents:</b> Multi-model agents with configurable reasoning profiles",
        "<b>8 Logical Enhancements:</b> ChromaDB, block binding, API routing, auto-suggest, and more",
        "<b>Complete API:</b> 50+ RESTful endpoints for all features",
        "<b>Modular Architecture:</b> Clean separation of concerns, extensible design",
        "<b>Production Ready:</b> 95% complete backend, scalable infrastructure"
    ]
    
    for feature in features:
        story.append(Paragraph(f"• {feature}", body_style))
    
    story.append(PageBreak())
    
    # Section 2: Quick Start
    story.append(Paragraph("2. Quick Start Guide (30 Minutes)", heading1_style))
    story.append(Paragraph(
        "This guide will get you from zero to a running ML Filesystem backend in approximately 30 minutes.",
        body_style
    ))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Prerequisites", heading2_style))
    prereqs = [
        "Python 3.11 or higher",
        "pip (Python package manager)",
        "4GB RAM minimum (8GB recommended)",
        "5GB disk space minimum",
        "Internet connection for dependencies"
    ]
    for prereq in prereqs:
        story.append(Paragraph(f"✓ {prereq}", body_style))
    
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("Step 1: Setup Virtual Environment (3 minutes)", heading2_style))
    story.append(Paragraph("<font face='Courier' size='9'>python3 -m venv venv</font>", code_style))
    story.append(Paragraph("<font face='Courier' size='9'>source venv/bin/activate</font>", code_style))
    
    story.append(Paragraph("Step 2: Install Dependencies (5-10 minutes)", heading2_style))
    story.append(Paragraph("<font face='Courier' size='9'>pip install --upgrade pip</font>", code_style))
    story.append(Paragraph("<font face='Courier' size='9'>pip install -r requirements.txt</font>", code_style))
    
    story.append(Paragraph("Step 3: Apply Critical Fixes (5 minutes)", heading2_style))
    story.append(Paragraph(
        "<b>Fix 1:</b> Edit <font face='Courier'>core/database.py</font>, add after line 21:",
        body_style
    ))
    story.append(Paragraph(
        "<font face='Courier' size='8'>from core.enhanced_models import (APIConnection, ServiceType, "
        "CodingProject, CodeExecution, VMConfiguration, VMSnapshot)</font>",
        code_style
    ))
    
    story.append(Paragraph(
        "<b>Fix 2:</b> Edit <font face='Courier'>api/internal_api.py</font>, add before return app:",
        body_style
    ))
    story.append(Paragraph(
        "<font face='Courier' size='8'>from api.enhanced_routes import register_enhanced_routes<br/>"
        "register_enhanced_routes(app)</font>",
        code_style
    ))
    
    story.append(Paragraph(
        "<b>Fix 3:</b> Create missing __init__.py files:",
        body_style
    ))
    story.append(Paragraph(
        "<font face='Courier' size='8'>touch coding/__init__.py vm/__init__.py widgets/__init__.py "
        "workflows/__init__.py plugins/__init__.py</font>",
        code_style
    ))
    
    story.append(PageBreak())
    
    # Section 3: System Architecture
    story.append(Paragraph("3. System Architecture", heading1_style))
    story.append(Paragraph(
        "The ML Filesystem follows a layered architecture with clear separation of concerns.",
        body_style
    ))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Architectural Layers", heading2_style))
    
    layers_data = [
        ['Layer', 'Components', 'Purpose'],
        ['API Layer', 'Flask routes, Blueprints', 'External interface'],
        ['Feature Layer', 'Agents, IDE, VMs', 'High-level features'],
        ['ML Layer', 'Models, Training Blocks', 'ML infrastructure'],
        ['Filesystem Layer', 'Operations, Chains', 'File management'],
        ['Core Layer', 'Database, Config', 'Foundation']
    ]
    
    layers_table = Table(layers_data, colWidths=[1.5*inch, 2.5*inch, 2*inch])
    layers_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    
    story.append(layers_table)
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Key Design Principles", heading2_style))
    principles = [
        "<b>Modularity:</b> Each component is self-contained and replaceable",
        "<b>Extensibility:</b> 7 major extension point types for plugins and customization",
        "<b>Composability:</b> Data, models, and agents are first-class composable objects",
        "<b>Safety:</b> Sandboxed operations, validation at all layers",
        "<b>Performance:</b> Lazy loading, caching, incremental operations"
    ]
    
    for principle in principles:
        story.append(Paragraph(f"• {principle}", body_style))
    
    story.append(PageBreak())
    
    # Section 4: Component Inventory
    story.append(Paragraph("4. Complete Component Inventory", heading1_style))
    story.append(Paragraph("Status Summary", heading2_style))
    
    status_data = [
        ['Component', 'Status', 'Completeness'],
        ['Core Infrastructure', 'Complete', '100%'],
        ['Database Layer', 'Complete', '100%'],
        ['ML Infrastructure', 'Complete', '100%'],
        ['API Layer', 'Near Complete', '95%'],
        ['Enhanced Features', 'Complete', '100%'],
        ['Integration Layer', 'Partial', '70%'],
        ['User Interface', 'Partial', '30%']
    ]
    
    status_table = Table(status_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
    status_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1'))
    ]))
    
    story.append(status_table))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Core Modules (24 Python files)", heading2_style))
    modules = [
        "api/ - 4 files, 1,218 lines - API routes and management",
        "coding/ - 2 files, 600 lines - IDE manager",
        "core/ - 5 files, 1,148 lines - Config, database, exceptions",
        "filesystem/ - 2 files, 1,200 lines - File operations",
        "ml/ - 6 files, 4,400 lines - ML infrastructure",
        "vm/ - 2 files, 500 lines - VM management",
        "Root - 3 files, 650 lines - Integration and main app"
    ]
    
    for module in modules:
        story.append(Paragraph(f"• {module}", body_style))
    
    story.append(PageBreak())
    
    # Section 5: API Reference (Summary)
    story.append(Paragraph("5. API Reference (Summary)", heading1_style))
    story.append(Paragraph(
        "The system provides 50+ RESTful API endpoints organized by feature area.",
        body_style
    ))
    story.append(Spacer(1, 0.2*inch))
    
    api_categories = [
        ("Authentication", ["POST /api/auth/login", "POST /api/auth/logout", "GET /api/auth/me"]),
        ("Files", ["GET /api/files", "POST /api/files", "GET /api/files/<id>", "DELETE /api/files/<id>"]),
        ("Training Blocks", ["GET /api/training-blocks", "POST /api/training-blocks", 
                            "POST /api/training-blocks/<id>/toggle", "POST /api/training-blocks/<id>/train"]),
        ("Agents", ["GET /api/agents", "POST /api/agents", "POST /api/agents/<id>/query"]),
        ("API Connections", ["GET /api/connections", "POST /api/connections", "POST /api/connections/<id>/test"]),
        ("Coding IDE", ["GET /api/coding/projects", "POST /api/coding/projects/<id>/execute"]),
        ("VMs", ["GET /api/vms", "POST /api/vms/<id>/start", "POST /api/vms/<id>/stop"]),
        ("Enhancements", ["POST /api/enhancements/search", "GET /api/enhancements/suggest-blocks/<id>"])
    ]
    
    for category, endpoints in api_categories:
        story.append(Paragraph(f"<b>{category}</b>", heading2_style))
        for endpoint in endpoints:
            story.append(Paragraph(f"<font face='Courier' size='9'>{endpoint}</font>", body_style))
        story.append(Spacer(1, 0.1*inch))
    
    story.append(PageBreak())
    
    # Additional sections...
    story.append(Paragraph("6. Database Schema", heading1_style))
    story.append(Paragraph(
        "The system uses SQLite with 17 tables and well-defined relationships.",
        body_style
    ))
    
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("Core Tables (8)", heading2_style))
    core_tables = [
        "users - User accounts and authentication",
        "files - File metadata and content",
        "filechains - Grouped file sequences",
        "training_blocks - ML training data collections (CORE FEATURE)",
        "ml_agents - AI agent configurations",
        "tags - File categorization",
        "file_embeddings - Vector embeddings",
        "activity_logs - System audit trail"
    ]
    for table in core_tables:
        story.append(Paragraph(f"• {table}", body_style))
    
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("Enhanced Tables (5)", heading2_style))
    enhanced_tables = [
        "api_connections - External API configurations",
        "coding_projects - IDE project metadata",
        "code_executions - Execution history",
        "vm_configurations - Virtual machine configs",
        "vm_snapshots - VM state snapshots"
    ]
    for table in enhanced_tables:
        story.append(Paragraph(f"• {table}", body_style))
    
    story.append(PageBreak())
    
    # Conclusion
    story.append(Paragraph("Documentation Summary", heading1_style))
    story.append(Paragraph(
        "This PDF provides a comprehensive overview of the ML Filesystem v1.8+ system. "
        "For complete details including:",
        body_style
    ))
    
    complete_details = [
        "Complete 75,000-word technical audit",
        "Line-by-line code explanations",
        "Detailed troubleshooting guides",
        "Step-by-step reconstruction instructions",
        "Extension and plugin development guides"
    ]
    
    story.append(Spacer(1, 0.1*inch))
    for detail in complete_details:
        story.append(Paragraph(f"• {detail}", body_style))
    
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(
        "Please refer to the complete documentation package with all markdown files, "
        "source code, and the master audit conversation.",
        body_style
    ))
    
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("Package Information", heading2_style))
    story.append(Paragraph(f"<b>Generated:</b> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", body_style))
    story.append(Paragraph("<b>Version:</b> 1.0", body_style))
    story.append(Paragraph("<b>System:</b> ML Filesystem v1.8+", body_style))
    story.append(Paragraph("<b>Documentation Base:</b> Complete Technical Audit", body_style))
    
    # Build PDF
    doc.build(story)
    
    return pdf_file

if __name__ == '__main__':
    try:
        pdf_file = create_comprehensive_pdf()
        print(f"✓ PDF created successfully: {pdf_file}")
        print(f"  Size: {os.path.getsize(pdf_file) / 1024:.1f} KB")
    except Exception as e:
        print(f"✗ Error creating PDF: {e}")
        import traceback
        traceback.print_exc()
