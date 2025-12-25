/**
 * Main map component for abandoned homes visualization.
 * 
 * React Component Basics:
 * - Component: Reusable UI piece
 * - Props: Data passed from parent
 * - State: Component's internal data
 * - Hooks: Functions to add features (useState, useEffect, etc.)
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.heat';

// Fix Leaflet icon issue in React
// Comment: "Webpack breaks Leaflet's default icon paths, must fix manually"
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

/**
 * MapView Component
 * 
 * Features:
 * - Interactive map with multiple tile layers
 * - Click anywhere to predict
 * - Display confirmed locations as markers
 * - Heatmap overlay for predictions
 * - Drawing tools for search areas
 */
const MapView = ({ locations = [], predictions = [], onMapClick, onLocationClick }) => {
  // React State
  // Comment: "useState creates state variable + setter function"
  const [mapCenter, setMapCenter] = useState([42.3314, -83.0458]); // Detroit
  const [zoom, setZoom] = useState(12);
  const [selectedLayer, setSelectedLayer] = useState('satellite');
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [showClusters, setShowClusters] = useState(true);
  
  // Ref for map instance
  // Comment: "useRef persists value across renders without causing re-render"
  const mapRef = useRef(null);
  
  /**
   * Tile Layer Options
   * 
   * Tile Layers: Map images divided into 256x256 pixel tiles
   * - Enables fast loading (only visible tiles downloaded)
   * - Different providers offer different styles
   * 
   * FOSS Tile Providers:
   * - OpenStreetMap: Free, community-maintained
   * - Esri: Free satellite imagery
   * - CartoDB: Clean, customizable styles
   */
  const tileLayers = {
    osm: {
      url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      attribution: '© OpenStreetMap contributors',
      name: 'Streets'
    },
    satellite: {
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      attribution: '© Esri',
      name: 'Satellite'
    },
    dark: {
      url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
      attribution: '© CartoDB',
      name: 'Dark'
    }
  };
  
  /**
   * Handle map click
   * 
   * Event Handling in React:
   * - Events passed as props (onMapClick)
   * - Parent component handles the logic
   * - Child just reports the event
   */
  const handleMapClick = useCallback((e) => {
    // Comment: "useCallback memoizes function, prevents recreating on each render"
    const { lat, lng } = e.latlng;
    console.log(`Map clicked at: ${lat}, ${lng}`);
    
    if (onMapClick) {
      onMapClick({ latitude: lat, longitude: lng });
    }
  }, [onMapClick]);
  
  /**
   * Custom marker icons by status
   * 
   * Icon Colors:
   * - Red: Confirmed abandoned
   * - Yellow: Predicted (high probability)
   * - Green: Not abandoned (confirmed)
   * - Blue: Pending verification
   */
  const getMarkerIcon = (location) => {
    const colors = {
      confirmed_abandoned: '#ef4444', // red
      predicted: '#eab308',            // yellow
      confirmed_not: '#22c55e',        // green
      pending: '#3b82f6'               // blue
    };
    
    const color = colors[location.status] || colors.pending;
    
    // Create custom colored marker
    // Comment: "L.divIcon creates HTML-based icon instead of image"
    return L.divIcon({
      className: 'custom-marker',
      html: `
        <div style="
          background-color: ${color};
          width: 24px;
          height: 24px;
          border-radius: 50% 50% 50% 0;
          transform: rotate(-45deg);
          border: 2px solid white;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        "></div>
      `,
      iconSize: [24, 24],
      iconAnchor: [12, 24],
      popupAnchor: [0, -24]
    });
  };
  
  return (
    <div className="relative w-full h-full">
      {/* Map Container */}
      {/* Comment: "MapContainer initializes Leaflet map, only renders once" */}
      <MapContainer
        center={mapCenter}
        zoom={zoom}
        className="w-full h-full"
        ref={mapRef}
      >
        {/* Base Tile Layer */}
        <TileLayer
          url={tileLayers[selectedLayer].url}
          attribution={tileLayers[selectedLayer].attribution}
          maxZoom={19}
        />
        
        {/* Map Event Handlers */}
        <MapEventHandler onClick={handleMapClick} />
        
        {/* Location Markers */}
        {locations.map((location) => (
          <Marker
            key={location.id}
            position={[location.latitude, location.longitude]}
            icon={getMarkerIcon(location)}
            eventHandlers={{
              click: () => onLocationClick?.(location)
            }}
          >
            <Popup>
              <div className="p-2">
                <h3 className="font-bold text-lg">{location.address || 'Unknown Address'}</h3>
                <p className="text-sm text-gray-600">
                  Status: <span className="font-semibold">{location.status}</span>
                </p>
                <p className="text-sm text-gray-600">
                  Condition: {location.condition}
                </p>
                {location.probability && (
                  <p className="text-sm text-gray-600">
                    Probability: {(location.probability * 100).toFixed(1)}%
                  </p>
                )}
                <button
                  onClick={() => onLocationClick?.(location)}
                  className="mt-2 px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600"
                >
                  View Details
                </button>
              </div>
            </Popup>
          </Marker>
        ))}
        
        {/* Heatmap Layer */}
        {showHeatmap && predictions.length > 0 && (
          <HeatmapLayer predictions={predictions} />
        )}
        
        {/* Drawing Tools */}
        <DrawingTools onDrawComplete={handleDrawComplete} />
        
        {/* Scale Control */}
        {/* Comment: "Shows map scale in km/miles" */}
        <ScaleControl position="bottomleft" />
      </MapContainer>
      
      {/* Layer Selector */}
      <LayerSelector
        layers={tileLayers}
        selected={selectedLayer}
        onChange={setSelectedLayer}
      />
      
      {/* Controls Panel */}
      <ControlsPanel
        showHeatmap={showHeatmap}
        onToggleHeatmap={() => setShowHeatmap(!showHeatmap)}
        showClusters={showClusters}
        onToggleClusters={() => setShowClusters(!showClusters)}
      />
    </div>
  );
};

/**
 * Map Event Handler Component
 * 
 * useMap Hook: Access Leaflet map instance in child component
 * useMapEvents: Subscribe to map events
 */
const MapEventHandler = ({ onClick }) => {
  const map = useMap();
  
  useEffect(() => {
    // Comment: "Add click listener to map"
    map.on('click', onClick);
    
    // Cleanup function
    // Comment: "Remove listener when component unmounts (prevent memory leaks)"
    return () => {
      map.off('click', onClick);
    };
  }, [map, onClick]);
  
  return null; // This component doesn't render anything
};

/**
 * Heatmap Layer Component
 * 
 * Heatmap: Visualizes density/intensity across area
 * - Red: High probability
 * - Yellow: Medium
 * - Blue: Low
 */
const HeatmapLayer = ({ predictions }) => {
  const map = useMap();
  
  useEffect(() => {
    // Convert predictions to heatmap data format
    // Comment: "Format: [[lat, lng, intensity], ...]"
    const heatData = predictions.map(p => [
      p.latitude,
      p.longitude,
      p.probability // 0-1 value
    ]);
    
    // Create heatmap layer
    const heatLayer = L.heatLayer(heatData, {
      radius: 25,        // Pixel radius of influence
      blur: 15,          // Amount of blur
      maxZoom: 17,       // Max zoom for heatmap
      max: 1.0,          // Max intensity value
      gradient: {        // Color gradient
        0.0: 'blue',
        0.5: 'yellow',
        1.0: 'red'
      }
    });
    
    heatLayer.addTo(map);
    
    // Cleanup
    return () => {
      map.removeLayer(heatLayer);
    };
  }, [map, predictions]);
  
  return null;
};

/**
 * Drawing Tools Component
 * 
 * Allows user to draw shapes on map:
 * - Rectangle: Bounding box search
 * - Circle: Radius search
 * - Polygon: Custom area
 */
const DrawingTools = ({ onDrawComplete }) => {
  const map = useMap();
  
  useEffect(() => {
    // Comment: "Import leaflet-draw dynamically"
    import('leaflet-draw').then(() => {
      // Initialize drawing controls
      const drawnItems = new L.FeatureGroup();
      map.addLayer(drawnItems);
      
      const drawControl = new L.Control.Draw({
        edit: {
          featureGroup: drawnItems,
          remove: true
        },
        draw: {
          polygon: {
            allowIntersection: false,
            shapeOptions: {
              color: '#3b82f6',
              fillOpacity: 0.2
            }
          },
          rectangle: {
            shapeOptions: {
              color: '#3b82f6',
              fillOpacity: 0.2
            }
          },
          circle: {
            shapeOptions: {
              color: '#3b82f6',
              fillOpacity: 0.2
            }
          },
          marker: false,
          polyline: false,
          circlemarker: false
        }
      });
      
      map.addControl(drawControl);
      
      // Handle draw events
      map.on(L.Draw.Event.CREATED, (e) => {
        const layer = e.layer;
        drawnItems.addLayer(layer);
        
        // Extract coordinates based on shape type
        let area;
        if (e.layerType === 'rectangle' || e.layerType === 'polygon') {
          area = {
            type: e.layerType,
            coordinates: layer.getLatLngs()[0].map(ll => [ll.lat, ll.lng])
          };
        } else if (e.layerType === 'circle') {
          const center = layer.getLatLng();
          const radius = layer.getRadius();
          area = {
            type: 'circle',
            center: [center.lat, center.lng],
            radius_meters: radius
          };
        }
        
        onDrawComplete?.(area);
      });
    });
  }, [map, onDrawComplete]);
  
  return null;
};

export default MapView;
