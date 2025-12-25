/**
 * Main App component - routing and layout
 */

import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import MapView from './components/Map/MapView';
import LocationDetail from './components/Locations/LocationDetail';
import AdminDashboard from './pages/Admin';
import { useMapData } from './hooks/useMapData';
import { MapIcon, ChartBarSquareIcon } from '@heroicons/react/24/outline'; // Note: Heroicons v2 names might differ slightly, adjusted

function App() {
  return (
    <BrowserRouter>
      <div className="h-screen flex flex-col overflow-hidden">
        {/* Navigation */}
        <nav className="bg-gray-900 text-white p-4 shadow-md z-50">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-2 font-bold text-xl tracking-tight">
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-teal-400">
                    EcoAsset
                </span>
                <span>Lab</span>
            </div>
            
            <div className="flex gap-6">
              <Link to="/" className="flex items-center gap-1 hover:text-blue-300 transition-colors">
                <MapIcon className="w-5 h-5" />
                <span>Map</span>
              </Link>
              <Link to="/admin" className="flex items-center gap-1 hover:text-blue-300 transition-colors">
                <ChartBarSquareIcon className="w-5 h-5" />
                <span>Admin</span>
              </Link>
            </div>
          </div>
        </nav>
        
        {/* Routes */}
        <div className="flex-1 relative overflow-hidden">
          <Routes>
            <Route path="/" element={<MapPage />} />
            <Route path="/admin" element={<AdminDashboard />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}

const MapPage = () => {
  const { locations, createLocation, refetch } = useMapData();
  const [selectedLocation, setSelectedLocation] = useState(null);
  
  const handleUpdate = async (id, data) => {
      // In a real app we'd call an update API
      console.log("Updating location", id, data);
      await refetch(); // refresh map data
  }

  return (
    <>
      <MapView
        locations={locations}
        onMapClick={(coords) => {
            // Optional: Could open a "Create Location" modal here
            console.log("Map clicked", coords);
        }}
        onLocationClick={setSelectedLocation}
      />
      
      {selectedLocation && (
        <LocationDetail
          location={selectedLocation}
          onClose={() => setSelectedLocation(null)}
          onUpdate={handleUpdate}
        />
      )}
    </>
  );
};

export default App;
