import { useState, useCallback } from 'react';
import { api, ApiError } from '../utils/api';
import { Book } from '../types';

interface FileUploadProps {
  onUploadSuccess: (sessionId: string, books: Book[]) => void;
}

function FileUpload({ onUploadSuccess }: FileUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string>('');

  const handleFile = useCallback(async (file: File) => {
    if (!file.name.endsWith('.sqlite3')) {
      setError('Please select a .sqlite3 file');
      return;
    }

    setIsUploading(true);
    setError('');

    try {
      const uploadResponse = await api.uploadFile(file);
      const booksResponse = await api.getBooks(uploadResponse.session_id);
      onUploadSuccess(uploadResponse.session_id, booksResponse.books);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Upload failed. Please try again.');
      }
    } finally {
      setIsUploading(false);
    }
  }, [onUploadSuccess]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFile(files[0]);
    }
  }, [handleFile]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFile(files[0]);
    }
  }, [handleFile]);

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-4 text-center">
        <h2 className="mb-2 text-xl font-bold text-dark-100">
          Select KOReader Statistics Database
        </h2>
        <p className="text-dark-300">
          Upload your KOReader statistics database (.sqlite3 file) to begin merging book entries.
        </p>
      </div>

      <div className="p-4 card">
        <div
          className={`
            border-2 border-dashed rounded-lg p-6 text-center transition-all duration-200
            ${isDragOver 
              ? 'border-primary-400 bg-primary-400/10' 
              : 'border-dark-600 hover:border-dark-500'
            }
            ${isUploading ? 'opacity-50 pointer-events-none' : ''}
          `}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
        >
          {isUploading ? (
            <div className="space-y-3">
              <div className="w-10 h-10 mx-auto border-b-2 rounded-full animate-spin border-primary-500"></div>
              <p className="text-dark-300">Uploading and validating...</p>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="w-12 h-12 mx-auto text-dark-400">
                <svg fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM6.293 6.707a1 1 0 010-1.414l3-3a1 1 0 011.414 0l3 3a1 1 0 01-1.414 1.414L11 5.414V13a1 1 0 11-2 0V5.414L7.707 6.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
                </svg>
              </div>
              <div>
                <p className="mb-2 text-base text-dark-200">
                  Drag & drop your .sqlite3 file here
                </p>
                <p className="mb-3 text-dark-400">or</p>
                <label className="cursor-pointer px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors inline-block">
                  Choose File
                  <input
                    type="file"
                    accept=".sqlite3"
                    onChange={handleFileInput}
                    className="hidden"
                  />
                </label>
              </div>
              <p className="text-sm text-dark-400">
                Only .sqlite3 files are supported
              </p>
            </div>
          )}
        </div>

        {error && (
          <div className="p-4 mt-4 border border-red-700 rounded-lg bg-red-900/30">
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}
      </div>

      {/* Important Notice */}
      <div className="p-3 mt-4 border border-yellow-700 rounded-lg bg-yellow-900/30">
        <div className="flex items-start space-x-2">
          <svg className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
          <div>
            <h3 className="mb-1 font-semibold text-yellow-300 text-sm">Important Notice</h3>
            <p className="text-xs leading-relaxed text-yellow-200">
              <strong>After you upload your KOReader database, you'll have 2 hours to use it. Once that time's up, the file will be automatically deleted, and you'll need to upload it again if you want to keep going. Don't worry—any book covers you picked will stay saved in your browser, so you won't lose them</strong>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default FileUpload;
