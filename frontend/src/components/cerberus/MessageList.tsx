'use client';

import { useRef, useEffect, useMemo } from 'react';
import type { ConversationMessageItem } from '@/types/cerberus';
import { CitationList } from './CitationList';
import { ImplementButton } from './ImplementButton';
import { extractJson, parseStrategySpec } from '@/lib/strategy-spec';

function hasValidStrategyJson(text: string | null): boolean {
  if (!text) return false;
  const jsonStr = extractJson(text);
  if (!jsonStr) return false;
  const result = parseStrategySpec(text);
  return result.ok;
}

interface MessageListProps {
  messages: ConversationMessageItem[];
  streamingContent: string;
  isStreaming: boolean;
}

export function MessageList({ messages, streamingContent, isStreaming }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  if (messages.length === 0 && !isStreaming) {
    return (
      <div className="flex-1 flex items-center justify-center text-center px-6">
        <div className="text-muted-foreground">
          <p className="text-sm font-medium">No messages yet</p>
          <p className="text-xs mt-1">Start a conversation with Cerberus.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          <div
            className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
              msg.role === 'user'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-foreground'
            }`}
          >
            <p className="whitespace-pre-wrap">{msg.contentMd}</p>
            {msg.citations.length > 0 && <CitationList citations={msg.citations} />}
            {msg.role === 'assistant' && hasValidStrategyJson(msg.contentMd) && (
              <ImplementButton messageContent={msg.contentMd!} />
            )}
          </div>
        </div>
      ))}

      {isStreaming && streamingContent && (
        <div className="flex justify-start">
          <div className="max-w-[85%] rounded-lg px-3 py-2 text-sm bg-muted text-foreground">
            <p className="whitespace-pre-wrap">{streamingContent}</p>
            <span className="inline-block w-1.5 h-4 bg-primary/60 animate-pulse ml-0.5" />
          </div>
        </div>
      )}

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
