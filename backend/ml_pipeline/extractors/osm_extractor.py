"""
OpenStreetMap Extractor
======================

This module extracts spatial features from OpenStreetMap (OSM) using `osmnx`.
It analyzes the built environment, local amenities, and connectivity.

Key Spatial Indicators for Abandonment:
- Isolation: Distance to main roads/highways
- Food Deserts: Distance to grocery stores
- Blight: Density of vacant/derelict land tags
- Disinvestment: Lack of amenities (shops, schools, etc.)
- Infrastructure: Poor street connectivity (dead ends)
"""

import logging
import osmnx as ox
import networkx as nx
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from shapely.geometry import Point

logger = logging.getLogger(__name__)

# Configure OSMnx
ox.settings.use_cache = True
ox.settings.log_console = False

class OSMExtractor:
    """
    Extracts road network and POI features from OpenStreetMap.
    """

    def __init__(self):
        # Define amenities to look for
        self.poi_tags = {
            'amenity': [
                'school', 'hospital', 'police', 'fire_station', 
                'restaurant', 'cafe', 'bank', 'pharmacy'
            ],
            'shop': ['supermarket', 'convenience'],
            'leisure': ['park']
        }
        
        # Tags that specifically might indicate trouble
        self.risk_tags = {
            'landuse': ['brownfield', 'construction', 'landfill'],
            'building': ['ruins', 'vacant', 'derelict']
        }

    def extract_features(
        self, 
        latitude: float, 
        longitude: float, 
        radius_meters: int = 500
    ) -> Dict[str, Any]:
        """
        Main entry point.
         Downloads graph and POIs for the area.
        """
        features = {}
        
        try:
            # 1. Network / Graph Features
            # ---------------------------
            # Download street network (drive+walk)
            # This can be slow, so we use a small radius
            G = ox.graph_from_point(
                (latitude, longitude), 
                dist=radius_meters, 
                network_type='all'
            )
            
            # Calculate basic stats
            stats = ox.basic_stats(G)
            
            # Convert area to sq km for density calcs
            area_km2 = (np.pi * radius_meters**2) / 1_000_000
            
            features['road_network_density'] = stats.get('edge_length_total', 0) / 1000 / area_km2
            features['intersection_density'] = stats.get('intersection_count', 0) / area_km2
            features['average_street_length'] = stats.get('edge_length_avg', 0)
            features['dead_end_count'] = stats.get('streets_per_node_counts', {}).get(1, 0)
            
            # Connectivity (Node degree avg)
            features['street_connectivity'] = stats.get('k_avg', 0)

            # 2. Points of Interest
            # ---------------------
            # Get POIs within radius
            pois = ox.features_from_point(
                (latitude, longitude), 
                tags=self.poi_tags, 
                dist=radius_meters
            )
            
            if not pois.empty:
                # Count amenities
                features['amenity_count_total'] = len(pois)
                
                # Filter specific counts
                features['restaurant_count'] = len(pois[pois['amenity'] == 'restaurant']) if 'amenity' in pois.columns else 0
                features['school_count'] = len(pois[pois['amenity'] == 'school']) if 'amenity' in pois.columns else 0
                
                # Check for grocery stores (food desert indicator)
                # Note: 'shop' column might not exist if no shops found
                grocery_count = 0
                if 'shop' in pois.columns:
                    grocery_count = len(pois[pois['shop'].isin(['supermarket', 'convenience'])])
                features['grocery_store_count'] = grocery_count
                
                # Calculate distance to nearest POI of each type
                # For this demo, we'll just check presence/count 
                # Calculating exact distances requires CRS projection logic
            else:
                 features['amenity_count_total'] = 0
                 features['restaurant_count'] = 0
                 features['school_count'] = 0
                 features['grocery_store_count'] = 0

            # 3. Building Density
            # -------------------
            try:
                # Smaller radius for buildings to save time
                buildings = ox.features_from_point(
                    (latitude, longitude), 
                    tags={'building': True}, 
                    dist=min(radius_meters, 200)
                )
                features['building_count_200m'] = len(buildings)
            except Exception:
                # No buildings found or error
                features['building_count_200m'] = 0

        except Exception as e:
            logger.error(f"Error extracting OSM features: {e}")
            features['error_osm'] = str(e)
            
        return features
