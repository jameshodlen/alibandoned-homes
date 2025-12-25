/**
 * Admin dashboard for system management
 */

import React, { useState } from 'react';
import { useAdmin } from '../hooks/useAdmin';
import { ArrowPathIcon, ServerStackIcon, CheckBadgeIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';

const AdminDashboard = () => {
  const { stats, models, triggerTraining, activateModel, loading, error } = useAdmin();
  const [trainingStatus, setTrainingStatus] = useState(null);
  
  const handleTrain = async () => {
      const result = await triggerTraining('auto');
      if (result) {
          setTrainingStatus(`Training queued: Job ${result.job_id}`);
          setTimeout(() => setTrainingStatus(null), 5000);
      }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto bg-gray-50 min-h-screen">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Admin Dashboard</h1>
        {loading && <span className="text-sm text-gray-500 flex items-center gap-2"><ArrowPathIcon className="w-4 h-4 animate-spin"/> Updating...</span>}
      </div>

      {error && (
          <div className="bg-red-50 border-l-4 border-red-500 p-4 mb-6">
              <div className="flex">
                  <div className="flex-shrink-0">
                      <ExclamationTriangleIcon className="h-5 w-5 text-red-400" aria-hidden="true" />
                  </div>
                  <div className="ml-3">
                      <p className="text-sm text-red-700">{error}</p>
                  </div>
              </div>
          </div>
      )}
      
      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard 
            title="Total Locations" 
            value={stats?.locations?.total || 0} 
            icon={<ServerStackIcon className="w-6 h-6 text-blue-500"/>}
        />
        <StatCard 
            title="Confirmed" 
            value={stats?.locations?.confirmed || 0} 
            icon={<CheckBadgeIcon className="w-6 h-6 text-green-500"/>}
        />
        <StatCard 
            title="Unconfirmed" 
            value={stats?.locations?.unconfirmed || 0} 
            icon={<ExclamationTriangleIcon className="w-6 h-6 text-yellow-500"/>}
        />
        <StatCard 
            title="Active Model" 
            value={stats?.ml_model?.active_version || 'N/A'} 
            subtext={`Accuracy: ${(stats?.ml_model?.accuracy * 100)?.toFixed(1)}%`}
        />
      </div>
      
      {/* Model Management */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-8">
        <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-semibold text-gray-800">Model Management</h2>
            <button
                onClick={handleTrain}
                className={`flex items-center gap-2 px-4 py-2 rounded text-white text-sm font-medium transition-colors
                    ${loading ? 'bg-gray-400 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700'}`}
                disabled={loading}
            >
                <ArrowPathIcon className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                Trigger Retraining
            </button>
        </div>
        
        {trainingStatus && (
            <div className="mb-4 text-green-600 bg-green-50 p-2 rounded text-sm px-3 border border-green-100">
                {trainingStatus}
            </div>
        )}
        
        <ModelTable 
          models={models}
          onActivate={activateModel}
          loading={loading}
        />
      </div>
      
      {/* Placeholder for Performance Charts */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 flex items-center justify-center h-64 text-gray-400">
          Performance Charts Visualization Placeholder
      </div>
    </div>
  );
};

const StatCard = ({ title, value, icon, subtext }) => (
  <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5 flex flex-col justify-between h-32">
    <div className="flex justify-between items-start">
        <div className="text-sm font-medium text-gray-500 uppercase tracking-wide">{title}</div>
        {icon && <div className="p-2 bg-gray-50 rounded-lg">{icon}</div>}
    </div>
    <div>
        <div className="text-2xl font-bold text-gray-900">{value}</div>
        {subtext && <div className="text-xs text-green-600 mt-1">{subtext}</div>}
    </div>
  </div>
);

const ModelTable = ({ models, onActivate }) => (
  <div className="overflow-x-auto">
    <table className="w-full text-sm text-left">
        <thead className="text-xs text-gray-700 uppercase bg-gray-50 border-b">
        <tr>
            <th className="px-6 py-3">Version</th>
            <th className="px-6 py-3">Created</th>
            <th className="px-6 py-3">Metrics</th>
            <th className="px-6 py-3">Samples</th>
            <th className="px-6 py-3">Status</th>
            <th className="px-6 py-3">Actions</th>
        </tr>
        </thead>
        <tbody>
        {models && models.length > 0 ? (
            models.map(model => (
                <tr key={model.id} className="bg-white border-b hover:bg-gray-50">
                    <td className="px-6 py-4 font-medium text-gray-900">{model.version}</td>
                    <td className="px-6 py-4 text-gray-500">{new Date(model.created_at).toLocaleDateString()}</td>
                    <td className="px-6 py-4">
                        <div className="flex flex-col gap-1 text-xs">
                            <span title="Accuracy">Acc: {model.metrics?.accuracy.toFixed(2)}</span>
                            <span title="F1 Score">F1: {model.metrics?.f1_score.toFixed(2)}</span>
                        </div>
                    </td>
                    <td className="px-6 py-4 text-gray-500">{model.training_samples}</td>
                    <td className="px-6 py-4">
                        {model.is_active ? (
                        <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs font-medium">
                            Active
                        </span>
                        ) : (
                        <span className="px-2 py-1 bg-gray-100 text-gray-800 rounded-full text-xs font-medium">
                            Inactive
                        </span>
                        )}
                    </td>
                    <td className="px-6 py-4">
                        {!model.is_active && (
                        <button
                            onClick={() => onActivate(model.version)}
                            className="text-indigo-600 hover:text-indigo-900 font-medium"
                        >
                            Activate
                        </button>
                        )}
                    </td>
                </tr>
            ))
        ) : (
            <tr>
                <td colSpan="6" className="px-6 py-8 text-center text-gray-500">
                    No models found.
                </td>
            </tr>
        )}
        </tbody>
    </table>
  </div>
);

export default AdminDashboard;
