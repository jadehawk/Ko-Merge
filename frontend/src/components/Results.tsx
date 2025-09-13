import { useState, useEffect } from 'react';
import { Book } from '../types';
import { formatTime } from '../utils/formatTime';
import { api, ApiError } from '../utils/api';

interface ResultsProps {
  sessionId: string;
  onStartOver: () => void;
  onDownloadComplete?: () => void;
}

function Results({ sessionId, onStartOver, onDownloadComplete }: ResultsProps) {
  const [books, setBooks] = useState<Book[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [isDownloading, setIsDownloading] = useState(false);

  useEffect(() => {
    const fetchResults = async () => {
      try {
        const response = await api.getResult(sessionId);
        setBooks(response.books);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError('Failed to load results');
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchResults();
  }, [sessionId]);

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      const downloadUrl = api.getDownloadUrl(sessionId);
      
      // Create a temporary link to trigger download
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = 'statistics_fixed.sqlite3';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      // Notify parent component that download completed (to refresh counter)
      if (onDownloadComplete) {
        onDownloadComplete();
      }

      // Clean up session after download
      setTimeout(async () => {
        try {
          await api.cleanupSession(sessionId);
        } catch (err) {
          console.warn('Failed to cleanup session:', err);
        }
      }, 1000);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Download failed');
      }
    } finally {
      setIsDownloading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center py-16">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto mb-4"></div>
          <p className="text-dark-300">Loading results...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="card p-8 text-center">
          <div className="text-red-400 mb-4">
            <svg className="w-16 h-16 mx-auto" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
          </div>
          <h3 className="text-xl font-semibold text-dark-100 mb-2">Error Loading Results</h3>
          <p className="text-dark-300 mb-6">{error}</p>
          <button 
            onClick={onStartOver} 
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
          >
            Start Over
          </button>
        </div>
      </div>
    );
  }

  const totalReadingTime = books.reduce((total, book) => total + book.total_read_time, 0);

  return (
    <div className="space-y-8">
      {/* Success Header */}
      <div className="text-center">
        <div className="text-green-400 mb-4">
          <svg className="w-16 h-16 mx-auto" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
        </div>
        <h2 className="text-3xl font-bold text-dark-100 mb-2">Merge Complete!</h2>
        <p className="text-dark-300">
          Your KOReader statistics have been successfully merged. Download your updated database below.
        </p>
      </div>

      {/* Statistics Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card p-6 text-center">
          <div className="text-2xl font-bold text-primary-400 mb-2">{books.length}</div>
          <div className="text-dark-300">Books Remaining</div>
        </div>
        <div className="card p-6 text-center">
          <div className="text-2xl font-bold text-green-400 mb-2">
            {formatTime(totalReadingTime)}
          </div>
          <div className="text-dark-300">Total Reading Time</div>
        </div>
        <div className="card p-6 text-center">
          <div className="text-2xl font-bold text-blue-400 mb-2">
            {Math.round(totalReadingTime / 3600)} hrs
          </div>
          <div className="text-dark-300">Hours Read</div>
        </div>
      </div>

      {/* Download Section */}
      <div className="card p-8 text-center">
        <h3 className="text-xl font-semibold text-dark-100 mb-4">Download Your Merged Database</h3>
        <p className="text-dark-300 mb-6">
          Your merged statistics database is ready for download. Replace your original database with this file.
        </p>
        <div className="flex justify-center space-x-4">
          <button
            onClick={handleDownload}
            disabled={isDownloading}
            className={`px-6 py-3 font-semibold rounded-lg transition-colors ${
              isDownloading
                ? 'bg-gray-600 text-gray-300 cursor-not-allowed'
                : 'bg-green-600 hover:bg-green-700 text-white'
            }`}
          >
            {isDownloading ? (
              <div className="flex items-center space-x-2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                <span>Downloading...</span>
              </div>
            ) : (
              <div className="flex items-center space-x-2">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
                <span>Download statistics_fixed.sqlite3</span>
              </div>
            )}
          </button>
          <button 
            onClick={onStartOver} 
            className="px-6 py-3 bg-slate-600 hover:bg-slate-700 text-white font-semibold rounded-lg transition-colors"
          >
            Merge Another Database
          </button>
        </div>
      </div>

      {/* Results Table */}
      <div className="card p-6">
        <h3 className="text-xl font-semibold text-dark-100 mb-4">Final Book List</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-600">
                <th className="text-left py-3 px-4 text-dark-300 font-medium">ID</th>
                <th className="text-left py-3 px-4 text-dark-300 font-medium">Title</th>
                <th className="text-left py-3 px-4 text-dark-300 font-medium">Reading Time</th>
                <th className="text-left py-3 px-4 text-dark-300 font-medium">MD5</th>
              </tr>
            </thead>
            <tbody>
              {books.map((book) => (
                <tr key={book.id} className="table-row">
                  <td className="py-3 px-4 text-dark-200">{book.id}</td>
                  <td className="py-3 px-4 text-dark-100 font-medium">{book.title}</td>
                  <td className="py-3 px-4 text-dark-200">{formatTime(book.total_read_time)}</td>
                  <td className="py-3 px-4 text-dark-400 font-mono text-sm truncate max-w-xs">
                    {book.md5}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Important Notes */}
      <div className="bg-blue-900/30 border border-blue-700 rounded-lg p-6">
        <h4 className="text-blue-300 font-semibold mb-3">Important Notes:</h4>
        <ul className="text-blue-200 text-sm space-y-2 list-disc list-inside">
          <li>Back up your original database before replacing it</li>
          <li>The downloaded file should be placed in your KOReader's statistics directory</li>
          <li>Restart KOReader after replacing the database file</li>
          <li>Your reading progress and statistics have been preserved and merged</li>
        </ul>
      </div>
    </div>
  );
}

export default Results;
