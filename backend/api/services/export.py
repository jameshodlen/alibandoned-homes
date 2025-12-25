"""
Export Service for generating privacy-safe reports and data formats.

=============================================================================
PRIVACY & ETHICS IN ABANDONED PROPERTY DATA
=============================================================================

1. Data Minimization:
   - Only export strictly necessary fields.
   - Remove Personally Identifiable Information (PII) like owner names.

2. Coordinate Obfuscation (Fuzzing):
   - When sharing publicly, precise coordinates can lead to trespassing.
   - Strategy: Round to 3 decimal places (~110m precision).
   - "This provides neighborhood-level context without pinpointing the exact house."

3. Formats:
   - GeoJSON/KML: For mapping software (QGIS, Google Earth).
   - CSV: For data analysts.
   - PDF: For decision makers/stakeholders (easy to read reports).
=============================================================================
"""

import csv
import json
import io
import math
from typing import List, Dict, Any
from datetime import datetime

# Try to import reportlab for PDF generation
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

class ExportService:
    
    @staticmethod
    def fuzz_coordinates(lat: float, lon: float, precision: int = 3) -> tuple:
        """
        Round coordinates to specified decimal places for privacy.
        3 decimal places is approx 110 meters.
        """
        return round(lat, precision), round(lon, precision)

    def export_geojson(self, locations: List[Dict], obfuscate: bool = True) -> Dict:
        """Generate GeoJSON FeatureCollection"""
        features = []
        for loc in locations:
            lat = loc.get('latitude', 0)
            lon = loc.get('longitude', 0)
            
            if obfuscate:
                lat, lon = self.fuzz_coordinates(lat, lon)
                
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat]
                },
                "properties": {
                    "id": loc.get('id'),
                    "status": loc.get('status'),
                    "confidence": loc.get('prediction_score'),
                    "last_updated": str(loc.get('updated_at'))
                }
            })
            
        return {
            "type": "FeatureCollection",
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "obfuscated": obfuscate,
                "count": len(features)
            },
            "features": features
        }

    def export_kml(self, locations: List[Dict], obfuscate: bool = True) -> str:
        """Generate KML string for Google Earth"""
        kml = ['<?xml version="1.0" encoding="UTF-8"?>']
        kml.append('<kml xmlns="http://www.opengis.net/kml/2.2">')
        kml.append('<Document>')
        kml.append('<name>Abandoned Homes Prediction Export</name>')
        
        for loc in locations:
            lat = loc.get('latitude', 0)
            lon = loc.get('longitude', 0)
            
            if obfuscate:
                lat, lon = self.fuzz_coordinates(lat, lon)
                
            kml.append('<Placemark>')
            kml.append(f"<name>{loc.get('id', 'Unknown')}</name>")
            kml.append(f"<description>Status: {loc.get('status')}\nConfidence: {loc.get('prediction_score')}</description>")
            kml.append('<Point>')
            kml.append(f'<coordinates>{lon},{lat},0</coordinates>')
            kml.append('</Point>')
            kml.append('</Placemark>')
            
        kml.append('</Document>')
        kml.append('</kml>')
        
        return "\n".join(kml)

    def export_csv(self, locations: List[Dict], obfuscate: bool = True) -> str:
        """Generate CSV string"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['ID', 'Latitude', 'Longitude', 'Status', 'Confidence', 'Updated'])
        
        for loc in locations:
            lat = loc.get('latitude', 0)
            lon = loc.get('longitude', 0)
            
            if obfuscate:
                lat, lon = self.fuzz_coordinates(lat, lon)
                
            writer.writerow([
                loc.get('id'),
                lat,
                lon,
                loc.get('status'),
                loc.get('prediction_score'),
                loc.get('updated_at')
            ])
            
        return output.getvalue()

    def generate_pdf_report(self, locations: List[Dict], output_path: str, obfuscate: bool = False):
        """Generate a PDF summary report"""
        if not HAS_REPORTLAB:
            raise ImportError("reportlab library is required for PDF generation")

        doc = SimpleDocTemplate(output_path, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()

        # Title
        elements.append(Paragraph("Abandoned Homes Analysis Report", styles['Title']))
        elements.append(Spacer(1, 12))
        
        # Meta info
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
        elements.append(Paragraph(f"Total Locations: {len(locations)}", styles['Normal']))
        elements.append(Paragraph(f"Obfuscated Coordinates: {'Yes' if obfuscate else 'No'}", styles['Normal']))
        elements.append(Spacer(1, 24))

        # Table Data
        data = [['ID', 'Status', 'Confidence', 'Lat/Lon']]
        
        for loc in locations:
            lat = loc.get('latitude', 0)
            lon = loc.get('longitude', 0)
            if obfuscate:
                lat, lon = self.fuzz_coordinates(lat, lon)
            
            coords = f"{lat}, {lon}"
            data.append([
                str(loc.get('id'))[:8], # Short ID
                loc.get('status', 'Unknown'),
                f"{loc.get('prediction_score', 0):.2f}",
                coords
            ])

        # Table Style
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(table)
        
        # Build PDF
        doc.build(elements)
