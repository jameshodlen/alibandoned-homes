/**
 * Layer selector for switching base maps
 */

import React from 'react';

const LayerSelector = ({ layers, selected, onChange }) => {
  return (
    <div className="absolute top-4 right-4 bg-white rounded-lg shadow-lg p-2 z-[1000]">
      {/* Comment: "z-[1000] ensures it appears above map" */}
      <div className="text-sm font-semibold mb-2 px-2">Map Style</div>
      <div className="space-y-1">
        {Object.entries(layers).map(([key, layer]) => (
          <button
            key={key}
            onClick={() => onChange(key)}
            className={`
              w-full px-3 py-2 rounded text-left text-sm
              transition-colors duration-200
              ${selected === key
                ? 'bg-blue-500 text-white'
                : 'hover:bg-gray-100 text-gray-700'
              }
            `}
          >
            {layer.name}
          </button>
        ))}
      </div>
    </div>
  );
};

export default LayerSelector;
