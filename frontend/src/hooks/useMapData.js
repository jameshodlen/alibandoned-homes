/**
 * Custom hook for fetching map data
 * 
 * Custom Hooks: Reusable stateful logic
 * - Name starts with "use"
 * - Can use other hooks inside
 * - Returns data and functions
 */

import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const API_KEY = process.env.REACT_APP_API_KEY;

// Axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'X-API-Key': API_KEY
  }
});

export const useMapData = (bbox = null) => {
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  /**
   * Fetch locations from API
   */
  const fetchLocations = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const params = bbox ? { bbox } : {};
      const response = await api.get('/api/v1/locations', { params });
      
      setLocations(response.data);
    } catch (err) {
      console.error('Error fetching locations:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [bbox]);
  
  // Fetch on mount and when bbox changes
  useEffect(() => {
    fetchLocations();
  }, [fetchLocations]);
  
  /**
   * Create new location
   */
  const createLocation = useCallback(async (locationData) => {
    try {
      const response = await api.post('/api/v1/locations', locationData);
      
      // Add to state
      setLocations(prev => [...prev, response.data]);
      
      return response.data;
    } catch (err) {
      console.error('Error creating location:', err);
      throw err;
    }
  }, []);
  
  return {
    locations,
    loading,
    error,
    refetch: fetchLocations,
    createLocation
  };
};
