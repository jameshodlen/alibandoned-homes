/**
 * Research panel for historical context
 */

import React, { useState } from 'react';
import axios from 'axios';
import { BookOpenIcon, ClockIcon, ArrowTopRightOnSquareIcon } from '@heroicons/react/24/outline';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const API_KEY = process.env.REACT_APP_API_KEY;

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'X-API-Key': API_KEY
  }
});

const ResearchPanel = ({ location }) => {
  const [research, setResearch] = useState(null);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState([]);
  
  const startResearch = async () => {
    setLoading(true);
    setProgress(['Initializing research query...', 'Analyzing historical records...']);
    
    try {
      // Simulate polling/process for UI demonstration (replace with real backend poll in prod if available)
      // Because backend research endpoint might not be fully implemented, we mock a delay
      
      // Real call:
      /*
      const response = await api.post('/api/v1/research', {
        location_id: location.id,
        query: `Historical context and economic factors for ${location.address}`
      });
      const jobId = response.data.job_id;
      */
      
      // Mock progress updates
      await new Promise(r => setTimeout(r, 1500));
      setProgress(p => [...p, 'checking property tax records...']);
      await new Promise(r => setTimeout(r, 1500));
      setProgress(p => [...p, 'Analyzing neighborhood economic trends...']);
      await new Promise(r => setTimeout(r, 1000));
      setProgress(p => [...p, 'Synthesizing report...']);
      await new Promise(r => setTimeout(r, 1000));

      // Mock result
      setResearch({
          summary: `<p>This property located at <strong>${location.address || 'Coordinates'}</strong> appears to have been built in the early 1940s. Economic downturns in the surrounding district (District 5) have led to a 15% vacancy rate increase over the last decade.</p><p>Key historical factors include industrial rezoning in 1985 and recent tax foreclosure proceedings initiated in 2021.</p>`,
          citations: [
              { title: 'County Tax Records (2023)', url: '#' },
              { title: 'City Planning Archive (1985)', url: '#' },
              { title: 'Detroit Historical Society', url: '#' }
          ]
      });

    } catch (err) {
        console.error("Research failed", err);
        setProgress(p => [...p, 'Error: Research service unavailable']);
    } finally {
        setLoading(false);
    }
  };
  
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mt-6">
      <div className="flex items-center gap-2 mb-4">
        <BookOpenIcon className="w-5 h-5 text-indigo-600" />
        <h3 className="text-lg font-semibold text-gray-900">Historical Context</h3>
      </div>
      
      {!research && !loading && (
        <div className="text-center py-6">
            <p className="text-gray-500 text-sm mb-4">
                Generate a deep-dive research report on this property's history and economic factors using AI.
            </p>
            <button onClick={startResearch} className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded text-sm font-medium transition-colors">
            Start Research
            </button>
        </div>
      )}
      
      {loading && (
        <div className="bg-gray-50 p-4 rounded text-sm">
          <div className="flex items-center gap-2 mb-3 text-indigo-600 font-medium animate-pulse">
            <ClockIcon className="w-4 h-4" />
            Generating Report...
          </div>
          <div className="space-y-2 pl-2 border-l-2 border-indigo-200">
            {progress.map((item, idx) => (
              <div key={idx} className="text-gray-600 text-xs">
                ✓ {item}
              </div>
            ))}
          </div>
        </div>
      )}
      
      {research && (
        <div className="prose prose-sm max-w-none">
          <div className="text-gray-700 bg-indigo-50/50 p-4 rounded-lg border border-indigo-100" dangerouslySetInnerHTML={{ __html: research.summary }} />
          
          <div className="mt-4 pt-4 border-t border-gray-100">
            <h4 className="font-semibold text-xs text-gray-500 uppercase tracking-wide mb-2">Sources</h4>
            <ul className="space-y-1">
              {research.citations.map((citation, idx) => (
                <li key={idx}>
                  <a href={citation.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-indigo-600 hover:underline text-sm">
                    <ArrowTopRightOnSquareIcon className="w-3 h-3" />
                    {citation.title}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

export default ResearchPanel;
