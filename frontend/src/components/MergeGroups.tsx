import { useState } from 'react';
import { Book } from '../types';
import { formatTime } from '../utils/formatTime';
import { api, ApiError } from '../utils/api';
import BookCover from './BookCover';

interface MergeGroupsProps {
  books: Book[];
  sessionId: string;
  mergeGroups: [number, number[]][];
  onMergeGroupsChange: (groups: [number, number[]][]) => void;
  onMergeComplete: () => void;
}

function MergeGroups({ 
  books, 
  sessionId, 
  mergeGroups, 
  onMergeGroupsChange, 
  onMergeComplete 
}: MergeGroupsProps) {
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string>('');

  const getBookById = (id: number) => books.find(book => book.id === id);

  const removeGroup = (index: number) => {
    try {
      const newGroups = [...mergeGroups];
      newGroups.splice(index, 1);
      onMergeGroupsChange(newGroups);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    }
  };

  const clearAllGroups = async () => {
    try {
      await api.clearMergeGroups(sessionId);
      onMergeGroupsChange([]);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    }
  };

  const executeMerge = async () => {
    if (mergeGroups.length === 0) return;

    setIsExecuting(true);
    setError('');

    try {
      // Add all merge groups to the backend
      for (const [keepId, mergeIds] of mergeGroups) {
        await api.addMergeGroup(sessionId, {
          keep_id: keepId,
          merge_ids: mergeIds
        });
      }

      // Execute the merge
      await api.executeMerge(sessionId);
      onMergeComplete();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Merge failed. Please try again.');
      }
    } finally {
      setIsExecuting(false);
    }
  };

  if (mergeGroups.length === 0) {
    return (
      <div className="p-8 text-center bg-slate-800 border border-slate-600 rounded-lg">
        <div className="mb-4 text-slate-400">
          <svg className="w-16 h-16 mx-auto mb-4" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
          </svg>
        </div>
        <h3 className="mb-2 text-lg font-medium text-slate-200">No Merge Groups</h3>
        <p className="text-slate-400">
          Create merge groups by selecting books above, then execute all merges at once.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center">
        <h2 className="text-2xl font-bold text-slate-50">Merge Groups</h2>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4">
          <p className="text-red-300 text-sm">{error}</p>
        </div>
      )}

      {/* Merge Groups */}
      <div className="space-y-6">
        {mergeGroups.map(([keepId, mergeIds], index) => {
          const keepBook = getBookById(keepId);
          const mergeBooksData = mergeIds.map(id => getBookById(id)).filter((book): book is Book => book !== undefined);

          return (
            <div key={index} className="p-6 bg-slate-800 border border-slate-600 rounded-lg">
              <div className="flex justify-between items-start mb-6">
                <h3 className="text-lg font-semibold text-slate-200">
                  Merge Group {index + 1}
                </h3>
                <button
                  onClick={() => removeGroup(index)}
                  disabled={isExecuting}
                  className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                    isExecuting
                      ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                      : 'bg-red-600 hover:bg-red-700 text-white'
                  }`}
                  title="Remove this merge group"
                >
                  Cancel Group
                </button>
              </div>

              {/* Keep and Merge Sections - Side by Side on Large Screens */}
              <div className="flex flex-col lg:flex-row gap-6 mb-6">
                {/* Keep Book Section */}
                {keepBook && (
                  <div className="flex-1">
                    <div className="flex items-center mb-4">
                      <div className="w-4 h-4 bg-green-600 rounded-full mr-3"></div>
                      <h4 className="text-lg font-semibold text-green-400">KEEP BOOK</h4>
                    </div>
                    <div className="p-4 bg-green-500/10 border-2 border-green-500/30 rounded-lg">
                      <div className="flex justify-center">
                        <div className="relative border border-green-500 rounded-lg p-3 bg-green-900/20 w-36">
                          {/* Book Cover */}
                          <div className="mb-2">
                            <BookCover
                              title={keepBook.title}
                              authors={keepBook.authors}
                              bookId={keepBook.id}
                              sessionId={sessionId}
                              md5={keepBook.md5}
                              total_read_time={keepBook.total_read_time}
                              className="aspect-book"
                            />
                          </div>

                          {/* Title */}
                          <h5 className="text-sm font-semibold leading-tight text-slate-50 line-clamp-2 mb-1">
                            {keepBook.title}
                          </h5>

                          {/* MD5 Hash */}
                          <div className="text-center mb-2">
                            <div className="text-xs text-blue-200 mb-1">MD5</div>
                            <div className="font-mono text-xs text-slate-300 break-all line-clamp-2">
                              {keepBook.md5}
                            </div>
                          </div>

                          {/* Status Badge */}
                          <div className="absolute top-2 left-2">
                            <span className="px-2 py-1 text-xs font-medium rounded-full bg-green-600 text-white">
                              KEEP
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Merge Books Section */}
                {mergeBooksData.length > 0 && (
                  <div className="flex-1">
                    <div className="flex items-center mb-4">
                      <div className="w-4 h-4 bg-red-600 rounded-full mr-3"></div>
                      <h4 className="text-lg font-semibold text-red-400">MERGE BOOKS ({mergeBooksData.length})</h4>
                    </div>
                    <div className="p-4 bg-red-500/10 border-2 border-red-500/30 rounded-lg">
                      <div className="flex flex-wrap justify-center gap-3">
                        {mergeBooksData.map((book) => (
                          <div
                            key={book.id}
                            className="relative border border-red-500 rounded-lg p-3 bg-red-900/20 w-36"
                          >
                            {/* Book Cover */}
                            <div className="mb-2">
                              <BookCover
                                title={book.title}
                                authors={book.authors}
                                bookId={book.id}
                                sessionId={sessionId}
                                md5={book.md5}
                                total_read_time={book.total_read_time}
                                className="aspect-book"
                              />
                            </div>

                            {/* Title */}
                            <h5 className="text-sm font-semibold leading-tight text-slate-50 line-clamp-2 mb-1">
                              {book.title}
                            </h5>

                            {/* MD5 Hash */}
                            <div className="text-center mb-2">
                              <div className="text-xs text-blue-200 mb-1">MD5</div>
                              <div className="font-mono text-xs text-slate-300 break-all line-clamp-2">
                                {book.md5}
                              </div>
                            </div>

                            {/* Status Badge */}
                            <div className="absolute top-2 left-2">
                              <span className="px-2 py-1 text-xs font-medium rounded-full bg-red-600 text-white">
                                MERGE
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Summary */}
              <div className="pt-4 border-t border-slate-600">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-slate-400">
                    Total reading time to merge:
                  </span>
                  <span className="text-slate-200 font-medium">
                    {formatTime(
                      mergeBooksData.reduce((total, book) => total + book.total_read_time, 0)
                    )}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Action Buttons - Moved to bottom */}
      <div className="flex justify-center space-x-4 pt-6">
        <button
          onClick={clearAllGroups}
          disabled={isExecuting}
          className={`px-6 py-3 text-sm font-medium rounded-lg transition-colors ${
            isExecuting
              ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
              : 'bg-orange-600 hover:bg-orange-700 text-white'
          }`}
        >
          Clear All
        </button>
        <button
          onClick={executeMerge}
          disabled={isExecuting}
          className={`px-8 py-3 font-semibold rounded-lg transition-colors ${
            isExecuting
              ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
              : 'bg-green-600 hover:bg-green-700 text-white'
          }`}
        >
          {isExecuting ? (
            <div className="flex items-center space-x-2">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              <span>Processing...</span>
            </div>
          ) : (
            `Process Books (${mergeGroups.length} Group${mergeGroups.length > 1 ? 's' : ''})`
          )}
        </button>
      </div>

      {/* Warning */}
      <div className="bg-yellow-900/30 border border-yellow-700 rounded-lg p-4">
        <div className="flex items-start space-x-3">
          <svg className="w-5 h-5 text-yellow-400 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
          <div>
            <h4 className="text-yellow-300 font-medium mb-1">Warning</h4>
            <p className="text-yellow-200 text-sm">
              This operation will permanently delete the selected "MERGE BOOKS" from the KOReader's DB and combine reading statistics 
              with the "KEEP BOOK". Make sure you have a backup of your database before proceeding.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MergeGroups;
