'use client';

import { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ConversationMessageItem } from '@/types/copilot';
import { ToolStatusPill } from './ToolStatusPill';
import { CitationList } from './CitationList';
import { useCopilotStore } from '@/stores/copilot-store';

interface MessageListProps {
  messages: ConversationMessageItem[];
  streamingContent: string;
  isStreaming: boolean;
}

export function MessageList({ messages, streamingContent, isStreaming }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const { activeToolCalls } = useCopilotStore();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
      {messages.length === 0 && !isStreaming && (
        <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-3 opacity-50">
            <path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z" />
            <path d="M10 21h4" />
          </svg>
          <p className="text-sm font-medium">AI Copilot</p>
          <p className="text-xs mt-1 max-w-[250px]">
            Ask about your portfolio, strategies, risk, or market analysis.
          </p>
        </div>
      )}

      {messages.map((msg) => (
        <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
          <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm
            ${msg.role === 'user'
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-foreground'
            }`}
          >
            {msg.role === 'assistant' ? (
              <div className="prose prose-sm dark:prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {msg.contentMd || ''}
                </ReactMarkdown>
                {msg.citations.length > 0 && (
                  <CitationList citations={msg.citations} />
                )}
              </div>
            ) : (
              <p>{msg.contentMd}</p>
            )}
          </div>
        </div>
      ))}

      {/* Active tool calls */}
      {activeToolCalls.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {activeToolCalls.map((tc) => (
            <ToolStatusPill key={tc.toolName} toolCall={tc} />
          ))}
        </div>
      )}

      {/* Streaming content */}
      {isStreaming && streamingContent && (
        <div className="flex justify-start">
          <div className="max-w-[85%] rounded-lg px-3 py-2 text-sm bg-muted text-foreground">
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {streamingContent}
              </ReactMarkdown>
            </div>
          </div>
        </div>
      )}

      {/* Loading dots */}
      {isStreaming && !streamingContent && (
        <div className="flex justify-start">
          <div className="rounded-lg px-3 py-2 bg-muted">
            <div className="flex space-x-1">
              <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
