/**
 * Hook for admin functionality
 */

import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const API_KEY = process.env.REACT_APP_API_KEY;

// Axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'X-API-Key': API_KEY
  }
});

export const useAdmin = () => {
  const [stats, setStats] = useState(null);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const fetchStats = async () => {
    try {
      const response = await api.get('/api/v1/admin/stats');
      setStats(response.data);
    } catch (err) {
      console.error("Failed to fetch stats", err);
      // Fallback for demo if API fails
      setStats({
          locations: { total: 0, confirmed: 0 },
          models: { active_version: 'v1.0.0 (Demo)' }
      });
    }
  };
  
  const fetchModels = async () => {
    try {
      const response = await api.get('/api/v1/admin/models');
      setModels(response.data.versions || []);
    } catch (err) {
      console.error("Failed to fetch models", err);
      // Fallback/Mask error
      setModels([]); 
    }
  };
  
  const triggerTraining = async (strategy) => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.post('/api/v1/admin/models/train', null, { params: { strategy } });
      return response.data;
    } catch (err) {
      setError(err.response?.data?.detail || "Training trigger failed");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };
  
  const activateModel = async (versionId) => {
    setLoading(true);
    try {
      await api.post(`/api/v1/admin/models/${versionId}/activate`);
      await fetchModels(); // Refresh list
    } catch (err) {
      setError("Failed to activate model");
      console.error(err);
    } finally {
        setLoading(false);
    }
  };
  
  useEffect(() => {
    fetchStats();
    fetchModels();
  }, []);
  
  return { stats, models, triggerTraining, activateModel, loading, error };
};
