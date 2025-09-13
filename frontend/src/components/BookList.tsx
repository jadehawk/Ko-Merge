import { useState } from 'react';
import { Book } from '../types';
import { formatTime } from '../utils/formatTime';
import BookCover from './BookCover';

interface BookListProps {
  books: Book[];
  sessionId: string;
  mergeGroups: [number, number[]][];
  onMergeGroupsChange: (groups: [number, number[]][]) => void;
}

/**
 * BookList component displaying books in a library-style grid layout
 * Features prominent MD5 display for merge selection assistance
 */
function BookList({ books, sessionId, mergeGroups, onMergeGroupsChange }: BookListProps) {
  const [keepSelection, setKeepSelection] = useState<number | null>(null);
  const [mergeSelections, setMergeSelections] = useState<Set<number>>(new Set());

  /**
   * Determine the current status of a book in the merge process
   */
  const getBookStatus = (bookId: number) => {
    // Check if book is a keep book in any group
    for (const [keepId] of mergeGroups) {
      if (keepId === bookId) return 'keep';
    }
    
    // Check if book is in merge list of any group
    for (const [, mergeIds] of mergeGroups) {
      if (mergeIds.includes(bookId)) return 'merge';
    }
    
    return 'available';
  };

  /**
   * Handle selection of a book to keep (radio button behavior)
   */
  const handleKeepSelection = (bookId: number) => {
    setKeepSelection(keepSelection === bookId ? null : bookId);
    setMergeSelections(new Set());
  };

  /**
   * Handle selection of books to merge (checkbox behavior)
   */
  const handleMergeSelection = (bookId: number) => {
    const newSelections = new Set(mergeSelections);
    if (newSelections.has(bookId)) {
      newSelections.delete(bookId);
    } else {
      newSelections.add(bookId);
    }
    setMergeSelections(newSelections);
  };


  /**
   * Get the appropriate styling classes for a book card based on its status
   */
  const getCardClasses = (book: Book) => {
    const status = getBookStatus(book.id);
    const isKeepSelected = keepSelection === book.id;
    const isMergeSelected = mergeSelections.has(book.id);
    
    let classes = 'book-card bg-slate-800 border border-slate-600 rounded-lg p-3 cursor-pointer ';
    
    if (status === 'keep') {
      classes += 'selected-keep ';
    } else if (status === 'merge') {
      classes += 'selected-merge ';
    } else if (isKeepSelected) {
      classes += 'selected-keep ';
    } else if (isMergeSelected) {
      classes += 'selected-merge ';
    } else {
      classes += 'hover:border-blue-500 ';
    }
    
    return classes;
  };

  /**
   * Check if a book is available for selection
   */
  const isBookAvailable = (bookId: number) => {
    return getBookStatus(bookId) === 'available';
  };

  /**
   * Reset all selections
   */
  const resetSelections = () => {
    setKeepSelection(null);
    setMergeSelections(new Set());
  };

  /**
   * Add merge group (queue group)
   */
  const queueGroup = () => {
    if (keepSelection && mergeSelections.size > 0) {
      const newGroup: [number, number[]] = [keepSelection, Array.from(mergeSelections)];
      onMergeGroupsChange([...mergeGroups, newGroup]);
      resetSelections();
    }
  };

  const hasKeepSelection = keepSelection !== null;

  // Access global queue stats for progress display
  const queueStats = (window as any).__coverQueueStats || {
    totalBooks: 0,
    processed: 0,
    successful: 0,
    failed: 0,
    retryPending: 0,
    isProcessing: false,
    isPaused: false
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-3xl font-bold text-slate-50">Book Library</h2>
          <p className="mt-1 text-slate-400">
            Select books to merge • {books.length} books found
          </p>
        </div>
      </div>

      {/* Global Cover Loading Progress */}
      {queueStats.isProcessing && queueStats.totalBooks > 0 && (
        <div className="p-4 border rounded-lg bg-blue-900/20 border-blue-500/30">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-sm font-semibold text-blue-300">Loading Book Covers</h3>
              <p className="text-xs text-blue-400">
                Processing books sequentially for best results
              </p>
            </div>
            <div className="text-right">
              <div className="text-sm font-medium text-blue-300">
                {queueStats.processed} / {queueStats.totalBooks}
              </div>
              <div className="text-xs text-blue-400">
                {queueStats.successful} found, {queueStats.failed} failed
                {queueStats.retryPending > 0 && `, ${queueStats.retryPending} retries pending`}
              </div>
            </div>
          </div>
          
          {/* Progress Bar */}
          <div className="w-full bg-blue-900/50 rounded-full h-2">
            <div 
              className="bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{ 
                width: `${queueStats.totalBooks > 0 ? (queueStats.processed / queueStats.totalBooks) * 100 : 0}%` 
              }}
            ></div>
          </div>
          
          {/* Queue Controls */}
          <div className="flex gap-2 mt-3">
            <button
              onClick={() => {
                queueStats.isPaused = !queueStats.isPaused;
                // Force re-render by updating a dummy state if needed
              }}
              className="px-3 py-1 text-xs text-blue-300 transition-colors border border-blue-600 rounded hover:bg-blue-600/20"
            >
              {queueStats.isPaused ? '▶️ Resume' : '⏸️ Pause'}
            </button>
            <div className="text-xs text-blue-400 flex items-center">
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse mr-2"></div>
              Processing covers in display order...
            </div>
          </div>
        </div>
      )}

      {/* Queue Completion Message */}
      {!queueStats.isProcessing && queueStats.totalBooks > 0 && queueStats.processed === queueStats.totalBooks && (
        <div className="p-4 border rounded-lg bg-green-900/20 border-green-500/30">
          <div className="flex items-center gap-3">
            <div className="text-green-400 text-xl">✅</div>
            <div>
              <h3 className="text-sm font-semibold text-green-300">Cover Loading Complete</h3>
              <p className="text-xs text-green-400">
                Successfully loaded {queueStats.successful} covers, {queueStats.failed} books had no covers available
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Selection Instructions */}
      <div className="p-6 border rounded-lg bg-slate-800/50 border-slate-700">
        <h3 className="mb-3 text-lg font-semibold text-slate-200">How to Merge Books</h3>
        <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
          <div className="flex items-start space-x-3">
            <div className="w-4 h-4 bg-green-600 rounded-full mt-0.5 flex-shrink-0"></div>
            <div>
              <p className="font-medium text-green-400">Keep Book (Green)</p>
              <p className="text-slate-300">Click once to select the book you want to keep. This book will retain all metadata.</p>
            </div>
          </div>
          <div className="flex items-start space-x-3">
            <div className="w-4 h-4 bg-red-600 rounded-full mt-0.5 flex-shrink-0"></div>
            <div>
              <p className="font-medium text-red-400">Merge Books (Red)</p>
              <p className="text-slate-300">Click to select books to merge into the keep book. These will be deleted after merging.</p>
            </div>
          </div>
        </div>
      </div>

      {/* Books Grid */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
        {books.map((book) => {
          const status = getBookStatus(book.id);
          const isKeepSelected = keepSelection === book.id;
          const isMergeSelected = mergeSelections.has(book.id);
          const isAvailable = isBookAvailable(book.id);
          const canSelectAsKeep = isAvailable || isKeepSelected;
          const canSelectAsMerge = hasKeepSelection && isAvailable && book.id !== keepSelection;

          return (
            <div
              key={book.id}
              className={`relative ${getCardClasses(book)}`}
              data-book-id={book.id}
              data-book-title={book.title}
              data-book-author={book.authors || ''}
            >
              {/* Book Information */}
              <div className="space-y-1">
                {/* Reading Time & ID */}
                <div className="flex items-center justify-between text-xs book-info-container text-slate-400">
                  <span>ID: {book.id}</span>
                  <span>{formatTime(book.total_read_time)}</span>
                </div>

                {/* Book Cover */}
                <div className="mb-2">
                  <BookCover
                    title={book.title}
                    authors={book.authors}
                    bookId={book.id}
                    sessionId={sessionId}
                    md5={book.md5}
                    total_read_time={book.total_read_time}
                    className="book-cover-small aspect-book"
                  />
                </div>

                {/* Title */}
                <div className="flex items-start book-title-container">
                  <h3 className="text-sm font-semibold leading-tight text-slate-50 line-clamp-2">
                    {book.title}
                  </h3>
                </div>

                {/* Authors */}
                <div className="flex items-start book-authors-container">
                  {book.authors ? (
                    <p className="text-xs text-slate-300 line-clamp-2">
                      <span className="text-slate-400">by</span> {book.authors}
                    </p>
                  ) : (
                    <div></div>
                  )}
                </div>

                {/* Series */}
                <div className="flex items-start book-series-container">
                  {book.series ? (
                    <p className="text-xs text-slate-400 line-clamp-2">
                      <span className="text-blue-400">Series:</span> {book.series}
                    </p>
                  ) : (
                    <div></div>
                  )}
                </div>

                {/* MD5 Hash - Prominently Displayed */}
                <div className="flex items-center justify-center book-md5-container">
                  <div className="w-full text-center md5-hash">
                    <div className="mb-1 text-xs text-blue-200">MD5 HASH</div>
                    <div className="font-mono text-xs break-all line-clamp-2">{book.md5}</div>
                  </div>
                </div>

                {/* Selection Controls */}
                <div className="flex pt-2 space-x-2 border-t border-slate-700">
                  {/* Keep Selection */}
                  <button
                    onClick={() => canSelectAsKeep && handleKeepSelection(book.id)}
                    disabled={!canSelectAsKeep}
                    className={`flex-1 py-2 px-3 rounded text-sm font-medium transition-all duration-200 ${
                      isKeepSelected || status === 'keep'
                        ? 'bg-green-600 text-white'
                        : canSelectAsKeep
                        ? 'bg-green-600/20 text-green-400 hover:bg-green-600/30 border border-green-600/30'
                        : 'bg-slate-700 text-slate-500 cursor-not-allowed'
                    }`}
                  >
                    {status === 'keep' ? '✓ Keeping' : isKeepSelected ? '✓ Keep' : 'Keep'}
                  </button>

                  {/* Merge Selection */}
                  <button
                    onClick={() => canSelectAsMerge && handleMergeSelection(book.id)}
                    disabled={!canSelectAsMerge}
                    className={`flex-1 py-2 px-3 rounded text-sm font-medium transition-all duration-200 ${
                      isMergeSelected || status === 'merge'
                        ? 'bg-red-600 text-white'
                        : canSelectAsMerge
                        ? 'bg-red-600/20 text-red-400 hover:bg-red-600/30 border border-red-600/30'
                        : 'bg-slate-700 text-slate-500 cursor-not-allowed'
                    }`}
                  >
                    {status === 'merge' ? '✓ Merging' : isMergeSelected ? '✓ Merge' : 'Merge'}
                  </button>
                </div>
              </div>

              {/* Overlay for Keep book when merge selections exist */}
              {isKeepSelected && mergeSelections.size > 0 && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 rounded-lg">
                  <button
                    onClick={queueGroup}
                    className="px-4 py-2 mb-2 text-sm font-semibold text-white transition-colors bg-blue-600 rounded-lg hover:bg-blue-700"
                  >
                    Queue Group ({mergeSelections.size} → 1)
                  </button>
                  <button
                    onClick={resetSelections}
                    className="px-4 py-1 text-xs text-slate-300 transition-colors bg-slate-700 rounded hover:bg-slate-600"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Empty State */}
      {books.length === 0 && (
        <div className="py-16 text-center">
          <div className="mb-4 text-6xl">📚</div>
          <h3 className="mb-2 text-xl font-semibold text-slate-300">No Books Found</h3>
          <p className="text-slate-400">Upload a KOReader database to get started.</p>
        </div>
      )}
    </div>
  );
}

export default BookList;
