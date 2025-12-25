/**
 * Drag-and-drop photo upload
 * 
 * File Upload Concepts:
 * - FormData: Multipart form data for files
 * - FileReader: Read file contents in browser
 * - Drag & Drop API: Native browser file drop
 */

import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { PhotoIcon, CloudArrowUpIcon, XCircleIcon } from '@heroicons/react/24/outline';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const API_KEY = process.env.REACT_APP_API_KEY;

const PhotoUpload = ({ locationId, onUploadComplete }) => {
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState([]);
  const [error, setError] = useState(null);
  
  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return;

    // Comment: "acceptedFiles: Array of File objects"
    
    // Create preview URLs
    const previews = acceptedFiles.map(file => ({
      file,
      preview: URL.createObjectURL(file)
      // Comment: "createObjectURL creates temporary URL for preview"
    }));
    setPreview(previews);
    setError(null);
    
    // Upload files
    setUploading(true);
    
    try {
      // Create FormData for multipart upload
      const formData = new FormData();
      acceptedFiles.forEach(file => {
        formData.append('files', file); // Note: Backend expects 'files' list
      });
      
      await axios.post(
        `${API_BASE_URL}/api/v1/photos/${locationId}/upload`,
        formData,
        {
          headers: { 
            'X-API-Key': API_KEY,
            'Content-Type': 'multipart/form-data'
          }
        }
      );
      
      onUploadComplete?.();
      setPreview([]);
    } catch (err) {
      console.error('Upload error:', err);
      setError('Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  }, [locationId, onUploadComplete]);
  
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': ['.jpeg', '.jpg', '.png', '.heic'] },
    maxSize: 10485760, // 10MB
    multiple: true
  });
  
  return (
    <div className="w-full">
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-lg p-6 text-center cursor-pointer
          transition-colors duration-200
          ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'}
        `}
      >
        <input {...getInputProps()} />
        {isDragActive ? (
            <div className="flex flex-col items-center text-blue-500">
             <CloudArrowUpIcon className="w-10 h-10 mb-2" />
             <p className="font-medium">Drop photos here...</p>
            </div>
        ) : (
          <div className="flex flex-col items-center text-gray-500">
            <PhotoIcon className="w-10 h-10 mb-2 text-gray-400" />
            <p className="font-medium text-gray-700">Drag & drop photos</p>
            <p className="text-xs mt-1">or click to select</p>
            <p className="text-xs text-gray-400 mt-2">Max 10MB per photo</p>
          </div>
        )}
      </div>
      
      {/* Error Message */}
      {error && (
        <div className="mt-2 text-sm text-red-600 flex items-center gap-1">
            <XCircleIcon className="w-4 h-4" />
            {error}
        </div>
      )}
      
      {/* Preview */}
      {preview.length > 0 && (
        <div className="mt-4 grid grid-cols-3 gap-2">
          {preview.map((item, idx) => (
            <div key={idx} className="relative group">
                <img
                src={item.preview}
                alt={`Preview ${idx}`}
                className="w-full h-24 object-cover rounded opacity-75 group-hover:opacity-100 transition-opacity"
                />
                {uploading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-30 rounded">
                        <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    </div>
                )}
            </div>
          ))}
        </div>
      )}
      
      {uploading && <div className="mt-2 text-center text-sm text-blue-600 animate-pulse">Uploading photos...</div>}
    </div>
  );
};

export default PhotoUpload;
