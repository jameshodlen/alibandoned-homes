/**
 * Location detail modal with photo gallery
 * 
 * Modal Pattern: Overlay component that blocks interaction with background
 * - Trap focus inside modal
 * - Close on Escape key
 * - Close on backdrop click
 */

import React, { useState } from 'react';
import { XMarkIcon, MapPinIcon, PhotoIcon } from '@heroicons/react/24/outline';
import PhotoUpload from './PhotoUpload';

const LocationDetail = ({ location, onClose, onUpdate }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({
    condition: location.condition,
    accessibility: location.accessibility,
    notes: location.notes
  });
  
  // Handle form input changes
  // Comment: "Controlled components: React controls input value via state"
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault(); // Prevent page reload
    await onUpdate(location.id, formData);
    setIsEditing(false);
  };

  const handleUploadComplete = () => {
    // Refresh location data or photos - in a real app, this would trigger a refetch
    // For now, we might rely on parent to handle updates or just show alert
    alert('Upload complete!'); 
    // Ideally call a prop like onRefresh()
  };
  
  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black bg-opacity-50"
        onClick={onClose}
      />
      
      {/* Modal Content */}
      <div className="relative min-h-screen flex items-center justify-center p-4">
        <div className="relative bg-white rounded-lg shadow-xl max-w-4xl w-full">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b">
            <h2 className="text-2xl font-bold flex items-center gap-2">
              <MapPinIcon className="w-6 h-6" />
              Location Details
            </h2>
            <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
              <XMarkIcon className="w-6 h-6" />
            </button>
          </div>
          
          {/* Content */}
          <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Photo Gallery & Upload */}
            <div>
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <PhotoIcon className="w-5 h-5" />
                Photos
              </h3>
              
              {/* Gallery Grid */}
              <div className="grid grid-cols-2 gap-2 mb-4">
                {location.photos && location.photos.length > 0 ? (
                  location.photos.map(photo => (
                    <img 
                      key={photo.id}
                      src={photo.url} 
                      alt="Location" 
                      className="w-full h-32 object-cover rounded"
                    />
                  ))
                ) : (
                  <div className="col-span-2 text-gray-400 text-center py-4 bg-gray-50 rounded">
                    No photos yet
                  </div>
                )}
              </div>

              {/* Upload Component */}
              <div className="mt-4">
                <h4 className="text-sm font-medium mb-2">Add Photos</h4>
                <PhotoUpload locationId={location.id} onUploadComplete={handleUploadComplete} />
              </div>
            </div>
            
            {/* Details Form */}
            <div>
              {isEditing ? (
                <form onSubmit={handleSubmit} className="space-y-4">
                  <FormSelect
                    label="Condition"
                    name="condition"
                    value={formData.condition}
                    onChange={handleChange}
                    options={[
                      { value: 'intact', label: 'Intact' },
                      { value: 'partial_collapse', label: 'Partial Collapse' },
                      { value: 'full_collapse', label: 'Full Collapse' }
                    ]}
                  />
                  
                  <FormSelect
                    label="Accessibility"
                    name="accessibility"
                    value={formData.accessibility}
                    onChange={handleChange}
                    options={[
                      { value: 'easy', label: 'Easy' },
                      { value: 'moderate', label: 'Moderate' },
                      { value: 'difficult', label: 'Difficult' },
                      { value: 'dangerous', label: 'Dangerous' }
                    ]}
                  />
                  
                  <FormTextarea
                    label="Notes"
                    name="notes"
                    value={formData.notes}
                    onChange={handleChange}
                    rows={4}
                  />
                  
                  <div className="flex gap-2 pt-4">
                    <button type="submit" className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded">Save</button>
                    <button type="button" onClick={() => setIsEditing(false)} className="bg-gray-200 hover:bg-gray-300 text-gray-800 px-4 py-2 rounded">
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <div className="space-y-4">
                   <div className="bg-gray-50 p-4 rounded-lg">
                    <div className="space-y-3">
                        <DetailRow label="Address" value={location.address || "Unknown"} />
                        <DetailRow label="Coordinates" value={`${location.latitude.toFixed(6)}, ${location.longitude.toFixed(6)}`} />
                        <DetailRow label="Condition" value={formatEnumValue(location.condition)} />
                        <DetailRow label="Accessibility" value={formatEnumValue(location.accessibility)} />
                        {location.confidence_score && (
                            <DetailRow label="Confidence" value={`${(location.confidence_score * 100).toFixed(1)}%`} />
                        )}
                        <DetailRow label="Notes" value={location.notes || 'No notes'} />
                        <DetailRow label="Added" value={new Date(location.created_at).toLocaleDateString()} />
                    </div>
                  </div>
                  
                  <button onClick={() => setIsEditing(true)} className="w-full bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded mt-4">
                    Edit Details
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const DetailRow = ({ label, value }) => (
  <div className="flex justify-between border-b border-gray-100 pb-2 last:border-0 last:pb-0">
    <span className="text-gray-500">{label}</span>
    <span className="font-medium text-gray-900">{value}</span>
  </div>
);

const FormSelect = ({ label, name, value, onChange, options }) => (
    <div className="flex flex-col">
        <label className="text-sm font-medium text-gray-700 mb-1">{label}</label>
        <select 
            name={name} 
            value={value} 
            onChange={onChange}
            className="border rounded p-2 focus:ring-2 focus:ring-blue-500 outline-none"
        >
            {options.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
        </select>
    </div>
)

const FormTextarea = ({ label, name, value, onChange, rows }) => (
    <div className="flex flex-col">
        <label className="text-sm font-medium text-gray-700 mb-1">{label}</label>
        <textarea 
            name={name} 
            value={value || ''} 
            onChange={onChange}
            rows={rows}
            className="border rounded p-2 focus:ring-2 focus:ring-blue-500 outline-none"
        />
    </div>
)

// Helper to format enum values (e.g. "partial_collapse" -> "Partial Collapse")
const formatEnumValue = (val) => {
    if (!val) return "Unknown";
    return val.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}

export default LocationDetail;
