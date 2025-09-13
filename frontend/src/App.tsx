import { useState, useEffect } from 'react';
import FileUpload from './components/FileUpload';
import BookList from './components/BookList';
import MergeGroups from './components/MergeGroups';
import Results from './components/Results';
import { Book } from './types';
import { api } from './utils/api';
import { 
  restoreSession, 
  storeSessionId, 
  shouldAttemptRestore,
  formatRemainingTime,
  cleanupSession,
  SessionInfo 
} from './utils/sessionManager';

type AppState = 'upload' | 'merge' | 'results' | 'restoring';

function App() {
  const [state, setState] = useState<AppState>('upload');
  const [sessionId, setSessionId] = useState<string>('');
  const [books, setBooks] = useState<Book[]>([]);
  const [mergeGroups, setMergeGroups] = useState<[number, number[]][]>([]);
  const [downloadCount, setDownloadCount] = useState<number>(0);
  
  // Session persistence state
  const [sessionInfo, setSessionInfo] = useState<SessionInfo | null>(null);
  const [showSessionRestoredBanner, setShowSessionRestoredBanner] = useState<boolean>(false);

  // Function to refresh download counter
  const refreshDownloadCount = async () => {
    try {
      const response = await api.getDownloadCount();
      setDownloadCount(response.download_count);
      console.log('[App] Download counter refreshed:', response.download_count);
    } catch (error) {
      console.error('Failed to refresh download count:', error);
    }
  };

  // Session restoration and download count fetching on component mount
  useEffect(() => {
    const initializeApp = async () => {
      // Fetch download count
      await refreshDownloadCount();

      // Attempt session restoration if there's a stored session
      if (shouldAttemptRestore()) {
        console.log('[App] Attempting session restoration...');
        setState('restoring');

        try {
          const restoredSession = await restoreSession();
          
          if (restoredSession) {
            const { sessionId: restoredSessionId, sessionInfo: restoredSessionInfo } = restoredSession;
            
            // Fetch books for the restored session
            const booksResponse = await api.getBooks(restoredSessionId);
            
            // Restore application state
            setSessionId(restoredSessionId);
            setSessionInfo(restoredSessionInfo);
            setBooks(booksResponse.books);
            setMergeGroups(restoredSessionInfo.merge_groups);
            setShowSessionRestoredBanner(true); // Show the banner when session is restored
            
            // Determine which state to restore to
            if (restoredSessionInfo.processed_file_exists) {
              setState('results');
              console.log('[App] Session restored to results state');
            } else {
              setState('merge');
              console.log('[App] Session restored to merge state');
            }
          } else {
            console.log('[App] Session restoration failed, starting fresh');
            setState('upload');
          }
        } catch (error) {
          console.error('[App] Error during session restoration:', error);
          setState('upload');
        }
      }
    };

    initializeApp();
  }, []);

  const handleUploadSuccess = (newSessionId: string, uploadedBooks: Book[]) => {
    // Store session ID for persistence
    storeSessionId(newSessionId);
    
    setSessionId(newSessionId);
    setBooks(uploadedBooks);
    setMergeGroups([]);
    setState('merge');
    
    console.log('[App] New session started and stored:', newSessionId);
  };

  const handleMergeComplete = () => {
    setState('results');
  };

  const handleStartOver = async () => {
    // Clean up current session if exists
    if (sessionId) {
      try {
        await cleanupSession(sessionId);
        console.log('[App] Session cleaned up on start over');
      } catch (error) {
        console.error('[App] Error cleaning up session:', error);
      }
    }
    
    setSessionId('');
    setBooks([]);
    setMergeGroups([]);
    setSessionInfo(null);
    setState('upload');
  };

  return (
    <div className="min-h-screen bg-dark-900">
      {/* Header */}
      <header className="bg-dark-800 border-b border-dark-700 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div>
              <h1 className="text-3xl font-bold text-primary-400">
                Ko-Merge<sub className="text-sm font-medium"> v2</sub>{' '}
                <span className="text-sm text-dark-400 font-normal">
                  ( [ {downloadCount} ] KOReader Databases Fixed!)
                </span>
              </h1>
              <p className="text-dark-300 mt-1">
                KOReader Statistics Database Merger
              </p>
            </div>
            <div className="flex items-center space-x-4">
              {state !== 'upload' && (
                <button
                  onClick={handleStartOver}
                  className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors duration-200"
                >
                  Start Over
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Session Status Bar */}
      {sessionInfo && state !== 'upload' && state !== 'restoring' && (
        <div className="bg-blue-900/20 border-b border-blue-500/30">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2">
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center space-x-4 text-blue-300">
                <span>📁 Session Active</span>
                <span>⏱️ {formatRemainingTime(sessionInfo.session_remaining_minutes)} remaining</span>
                {sessionInfo.merge_groups_count > 0 && (
                  <span>🔗 {sessionInfo.merge_groups_count} merge groups</span>
                )}
              </div>
              <div className="text-blue-400 text-xs">
                Files cleanup in {formatRemainingTime(sessionInfo.file_cleanup_remaining_minutes)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        {state === 'restoring' && (
          <div className="flex flex-col items-center justify-center py-12">
            <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4"></div>
            <h2 className="text-2xl font-bold text-slate-200 mb-2">Restoring Session</h2>
            <p className="text-slate-400 text-center max-w-md">
              We found your previous session and are restoring your work. This will only take a moment...
            </p>
          </div>
        )}

        {state === 'upload' && (
          <FileUpload onUploadSuccess={handleUploadSuccess} />
        )}

        {state === 'merge' && (
          <div className="space-y-8">
            {/* Session Restored Banner */}
            {showSessionRestoredBanner && sessionInfo && (
              <div className="bg-green-900/20 border border-green-500/30 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="flex-shrink-0">
                      <svg className="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-sm font-medium text-green-300">Session Restored Successfully</h3>
                      <p className="text-sm text-green-400">
                        Your previous work has been restored. You can continue where you left off.
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setShowSessionRestoredBanner(false)}
                    className="flex-shrink-0 ml-4 text-green-400 hover:text-green-300 transition-colors"
                    aria-label="Close banner"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>
            )}
            
            <BookList
              books={books}
              sessionId={sessionId}
              mergeGroups={mergeGroups}
              onMergeGroupsChange={setMergeGroups}
            />
            <MergeGroups
              books={books}
              sessionId={sessionId}
              mergeGroups={mergeGroups}
              onMergeGroupsChange={setMergeGroups}
              onMergeComplete={handleMergeComplete}
            />
          </div>
        )}

        {state === 'results' && (
          <Results 
            sessionId={sessionId} 
            onStartOver={handleStartOver} 
            onDownloadComplete={refreshDownloadCount}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="bg-dark-800 border-t border-dark-700 mt-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="text-center text-dark-400">
            <p>
              Made with ❤️ by{' '}
              <a
                href="https://techy-notes.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-400 hover:text-primary-300 transition-colors"
              >
                Jadehawk
              </a>
            </p>
            <p className="text-sm mt-2">
              Weekend Project - Vibe Coding - Backup your DataBase! - Use at your own RISK!
            </p>
            
            {/* Donation Button */}
            <div className="mt-4">
              <a
                href="https://buymeacoffee.com/jadehawk"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg font-medium transition-colors duration-200 shadow-lg hover:shadow-xl transform hover:scale-105"
              >                
                🍺 Buy Me a Beer
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
