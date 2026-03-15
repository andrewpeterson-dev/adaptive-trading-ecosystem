'use client';

import { useRef, useState } from 'react';
import { FileStack, FolderUp, Sparkles } from 'lucide-react';
import {
  finalizeDocument,
  getDocumentStatus,
  sendChatMessage,
  uploadDocument,
} from '@/lib/cerberus-api';
import { useCerberusStore } from '@/stores/cerberus-store';
import { useUIContextStore } from '@/stores/ui-context-store';
import { MessageList } from './MessageList';

interface UploadedDocState {
  id: string;
  name: string;
  status: 'uploading' | 'processing' | 'indexed' | 'failed';
  indexedAt?: string | null;
}

export function ResearchPanel() {
  const [query, setQuery] = useState('');
  const [isResearching, setIsResearching] = useState(false);
  const [uploadedDocs, setUploadedDocs] = useState<UploadedDocState[]>([]);
  const [isDragActive, setIsDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const {
    messages,
    addMessage,
    activeThreadId,
    setActiveThread,
    setActiveTab,
    isStreaming,
    streamingContent,
    setStrategySeedPrompt,
  } = useCerberusStore();
  const { pageContext } = useUIContextStore();
  const indexedDocumentIds = uploadedDocs
    .filter((doc) => doc.status === 'indexed')
    .map((doc) => doc.id);

  const handleResearch = async () => {
    if (!query.trim() || isResearching) return;
    setIsResearching(true);
    setError(null);
    let shouldClearQuery = false;

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
        attachments: indexedDocumentIds.length > 0 ? indexedDocumentIds : undefined,
      });
      shouldClearQuery = true;
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
      setError(error instanceof Error ? error.message : 'Research request failed');
    } finally {
      setIsResearching(false);
      if (shouldClearQuery) {
        setQuery('');
      }
    }
  };

  const uploadFiles = async (files: FileList | File[]) => {
    const list = Array.from(files);
    setError(null);

    for (const file of list) {
      const tempId = `upload-${Date.now()}-${file.name}`;
      setUploadedDocs((prev) => [
        ...prev,
        { id: tempId, name: file.name, status: 'uploading' },
      ]);

      try {
        const { documentId, uploadUrl, uploadHeaders } = await uploadDocument(
          file.name,
          file.type || 'application/octet-stream'
        );
        const uploadResponse = await fetch(uploadUrl, {
          method: 'PUT',
          headers: {
            'Content-Type': file.type || 'application/octet-stream',
            ...uploadHeaders,
          },
          body: file,
        });
        if (!uploadResponse.ok) {
          let detail = uploadResponse.statusText || 'Upload failed';
          try {
            const body = await uploadResponse.json();
            detail = body.detail || body.message || detail;
          } catch {
            // Ignore JSON parse failures and fall back to the status text.
          }
          throw new Error(detail);
        }
        await finalizeDocument(documentId);
        const status = await getDocumentStatus(documentId);

        setUploadedDocs((prev) =>
          prev.map((doc) =>
            doc.id === tempId
              ? {
                  id: documentId,
                  name: status.filename || file.name,
                  status: status.status as UploadedDocState['status'],
                  indexedAt: status.indexedAt,
                }
              : doc
          )
        );
      } catch (error) {
        console.error('Upload error:', error);
        setError(error instanceof Error ? error.message : 'Document upload failed');
        setUploadedDocs((prev) =>
          prev.map((doc) =>
            doc.id === tempId ? { ...doc, status: 'failed' } : doc
          )
        );
      }
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files?.length) return;
    await uploadFiles(files);
    e.target.value = '';
  };

  const handleImplementStrategy = () => {
    const readyDocs = uploadedDocs.filter((doc) => doc.status === 'indexed');
    if (!readyDocs.length) {
      setError('Index at least one research document before seeding a strategy.');
      return;
    }
    const docNames = readyDocs.map((doc) => doc.name).join(', ');
    setStrategySeedPrompt(
      `Create a builder-ready trading strategy from these uploaded research documents: ${docNames}. Preserve assumptions, cite document-specific constraints, and translate the result into executable entry, exit, and risk rules.`
    );
    setError(null);
    setActiveTab('strategy');
  };

  return (
    <div className="flex flex-col h-full">
      <div className="space-y-4 border-b border-border/60 p-4 sm:p-5">
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-foreground">Research Mode</h3>
          <p className="text-xs text-muted-foreground">
            Upload research, ask questions with citations, then hand the thesis into Strategy drafting when it is ready.
          </p>
        </div>

        <div
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragActive(true);
          }}
          onDragLeave={() => setIsDragActive(false)}
          onDrop={(event) => {
            event.preventDefault();
            setIsDragActive(false);
            if (event.dataTransfer.files.length > 0) {
              void uploadFiles(event.dataTransfer.files);
            }
          }}
          className={`app-inset rounded-[20px] border-dashed px-4 py-4 transition-colors ${
            isDragActive
              ? 'border-primary bg-primary/5'
              : 'bg-muted/10'
          }`}
        >
          <div className="flex items-start gap-3">
            <FolderUp className="mt-0.5 h-4 w-4 text-primary" />
            <div className="flex-1">
              <p className="text-sm font-medium text-foreground">Drag and drop research files</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                PDFs, DOCX, TXT, MD, CSV, XLS, XLSX, and JSON are supported. Uploaded documents stay attached to this research thread.
              </p>
            </div>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              className="hidden"
              accept=".pdf,.docx,.txt,.md,.markdown,.csv,.xls,.xlsx,.json"
              multiple
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="app-button-secondary h-9 px-4 text-xs"
            >
              Browse
            </button>
          </div>
        </div>

        {uploadedDocs.length > 0 && (
          <div className="app-inset rounded-[20px] p-3">
            <div className="flex items-center gap-2">
              <FileStack className="h-4 w-4 text-primary" />
              <p className="app-label">Uploaded Documents</p>
            </div>
            <div className="mt-3 space-y-2">
              {uploadedDocs.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between gap-3 rounded-2xl border border-border/60 bg-background/70 px-3 py-2.5"
                >
                  <div>
                    <p className="text-sm font-medium text-foreground">{doc.name}</p>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      {doc.indexedAt ? `Indexed ${new Date(doc.indexedAt).toLocaleString()}` : 'Waiting for indexing'}
                    </p>
                  </div>
                  <span
                    className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${
                      doc.status === 'indexed'
                        ? 'border-emerald-500/25 bg-emerald-500/12 text-emerald-300'
                        : doc.status === 'failed'
                          ? 'border-red-500/25 bg-red-500/12 text-red-200'
                          : 'border-amber-500/25 bg-amber-500/12 text-amber-300'
                    }`}
                  >
                    {doc.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="app-inset rounded-[20px] p-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="app-label">Implement Strategy</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                This does not deploy or trade. It opens the Strategy tab with a document-aware drafting prompt so Cerberus can turn your research into a builder-ready spec.
              </p>
            </div>
            <button
              onClick={handleImplementStrategy}
              disabled={uploadedDocs.length === 0}
              className="app-button-secondary h-9 px-4 text-xs text-primary disabled:opacity-40"
            >
              <span className="inline-flex items-center gap-1.5">
                <Sparkles className="h-3 w-3" />
                Implement strategy
              </span>
            </button>
          </div>
        </div>

        <div className="flex items-start gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleResearch()}
            placeholder="Research question..."
            className="app-input h-10 flex-1"
          />
          <button
            onClick={handleResearch}
            disabled={!query.trim() || isResearching}
            className="app-button-primary h-10 shrink-0 px-4 text-sm disabled:opacity-50"
          >
            {isResearching ? 'Working...' : 'Ask'}
          </button>
        </div>

        {error && (
          <div className="rounded-2xl border border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}
      </div>
      <MessageList messages={messages} streamingContent={streamingContent} isStreaming={isStreaming} />
    </div>
  );
}
