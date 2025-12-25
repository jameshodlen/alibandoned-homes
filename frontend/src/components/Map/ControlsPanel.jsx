/**
 * Map controls for toggling features
 */

import React from 'react';

const ControlsPanel = ({
  showHeatmap,
  onToggleHeatmap,
  showClusters,
  onToggleClusters
}) => {
  return (
    <div className="absolute bottom-4 left-4 bg-white rounded-lg shadow-lg p-4 z-[1000]">
      <h3 className="font-semibold mb-3">Map Layers</h3>
      
      {/* Toggle switches */}
      <div className="space-y-2">
        <ToggleSwitch
          label="Show Heatmap"
          checked={showHeatmap}
          onChange={onToggleHeatmap}
          description="Probability density overlay"
        />
        
        <ToggleSwitch
          label="Cluster Markers"
          checked={showClusters}
          onChange={onToggleClusters}
          description="Group nearby locations"
        />
      </div>
      
      {/* Legend */}
      <div className="mt-4 pt-4 border-t">
        <h4 className="text-sm font-semibold mb-2">Legend</h4>
        <div className="space-y-1 text-xs">
          <LegendItem color="#ef4444" label="Confirmed Abandoned" />
          <LegendItem color="#eab308" label="Predicted (High)" />
          <LegendItem color="#3b82f6" label="Pending Verification" />
          <LegendItem color="#22c55e" label="Not Abandoned" />
        </div>
      </div>
    </div>
  );
};

const ToggleSwitch = ({ label, checked, onChange, description }) => {
  return (
    <label className="flex items-center justify-between cursor-pointer">
      <div>
        <div className="font-medium text-sm">{label}</div>
        {description && (
          <div className="text-xs text-gray-500">{description}</div>
        )}
      </div>
      <div className="relative">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="sr-only"
        />
        {/* Comment: "Custom toggle switch styled with Tailwind" */}
        <div className={`
          w-11 h-6 rounded-full transition-colors
          ${checked ? 'bg-blue-500' : 'bg-gray-300'}
        `}>
          <div className={`
            w-4 h-4 rounded-full bg-white shadow-md
            transform transition-transform duration-200
            ${checked ? 'translate-x-6' : 'translate-x-1'}
            mt-1
          `} />
        </div>
      </div>
    </label>
  );
};

const LegendItem = ({ color, label }) => (
  <div className="flex items-center gap-2">
    <div
      className="w-3 h-3 rounded-full border border-white shadow"
      style={{ backgroundColor: color }}
    />
    <span>{label}</span>
  </div>
);

export default ControlsPanel;
