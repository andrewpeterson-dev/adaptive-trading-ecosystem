'use client';

import { useState, useRef } from 'react';
import { sendChatMessage } from '@/lib/copilot-api';
import { uploadDocument, finalizeDocument } from '@/lib/copilot-api';
import { useCopilotStore } from '@/stores/copilot-store';
import { useUIContextStore } from '@/stores/ui-context-store';
import { MessageList } from './MessageList';

export function ResearchPanel() {
  const [query, setQuery] = useState('');
  const [isResearching, setIsResearching] = useState(false);
  const [uploadedDocs, setUploadedDocs] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { messages, addMessage, activeThreadId, setActiveThread, isStreaming, streamingContent } = useCopilotStore();
  const { pageContext } = useUIContextStore();

  const handleResearch = async () => {
    if (!query.trim() || isResearching) return;
    setIsResearching(true);

    addMessage({
      id: `user-${Date.now()}`,
      role: 'user',
      contentMd: query,
      structuredJson: null,
      modelName: null,
      citations: [],
      toolCalls: [],
      createdAt: new Date().toISOString(),
    });

    try {
      const response = await sendChatMessage({
        threadId: activeThreadId || undefined,
        mode: 'research',
        message: query,
        pageContext,
        attachments: uploadedDocs.length > 0 ? uploadedDocs : undefined,
      });
      if (!activeThreadId) setActiveThread(response.threadId);
      if (response.message) {
        addMessage({
          id: response.turnId,
          role: 'assistant',
          contentMd: response.message.markdown || '',
          structuredJson: response.message,
          modelName: null,
          citations: response.message.citations || [],
          toolCalls: [],
          createdAt: new Date().toISOString(),
        });
      }
    } catch (error) {
      console.error('Research error:', error);
    } finally {
      setIsResearching(false);
      setQuery('');
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const { documentId } = await uploadDocument(file.name, file.type);
      await finalizeDocument(documentId);
      setUploadedDocs((prev) => [...prev, documentId]);
    } catch (error) {
      console.error('Upload error:', error);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 space-y-3 border-b border-border">
        <div>
          <h3 className="text-sm font-semibold text-foreground mb-1">Research Mode</h3>
          <p className="text-xs text-muted-foreground">Upload documents and ask research questions with citations.</p>
        </div>
        <div className="flex gap-2">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            className="hidden"
            accept=".pdf,.docx,.txt,.md,.csv,.xlsx"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="text-xs px-3 py-1.5 rounded-md border border-border hover:bg-muted transition-colors text-muted-foreground"
          >
            Upload Doc
          </button>
          {uploadedDocs.length > 0 && (
            <span className="text-xs text-muted-foreground self-center">
              {uploadedDocs.length} doc(s) attached
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleResearch()}
            placeholder="Research question..."
            className="flex-1 rounded-lg border border-border bg-muted/50 px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/50"
          />
          <button
            onClick={handleResearch}
            disabled={!query.trim() || isResearching}
            className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {isResearching ? '...' : 'Ask'}
          </button>
        </div>
      </div>
      <MessageList messages={messages} streamingContent={streamingContent} isStreaming={isStreaming} />
    </div>
  );
}
