'use client';

import React, { useRef, useEffect, memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
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

/** Strip excessive decorative characters the LLM sometimes adds */
function cleanContent(text: string): string {
  return text
    .replace(/^[-=]{3,}$/gm, '')       // horizontal rules (---, ===)
    .replace(/^[/\\|*]{3,}$/gm, '')    // decorative separators (///, ***, |||)
    .replace(/\n{3,}/g, '\n\n')        // collapse excess blank lines
    .trim();
}

/** Memoized single message bubble — only re-renders when message content changes. */
const MessageBubble = memo(function MessageBubble({ msg }: { msg: ConversationMessageItem }) {
  return (
    <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[88%] rounded-xl px-3.5 py-2.5 text-sm ${
          msg.role === 'user'
            ? 'bg-primary text-primary-foreground rounded-br-md'
            : msg.role === 'system'
              ? 'bg-red-500/10 border border-red-500/20 text-red-400 rounded-bl-md'
              : 'bg-muted/80 text-foreground rounded-bl-md'
        }`}
      >
        {msg.role === 'user' ? (
          <p className="whitespace-pre-wrap">{msg.contentMd}</p>
        ) : (
          <div className="cerberus-md prose prose-sm dark:prose-invert max-w-none
            [&_p]:my-1 [&_p]:text-foreground [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0.5 [&_li]:text-foreground
            [&_strong]:text-foreground [&_strong]:font-semibold
            [&_code]:text-xs [&_code]:bg-background/50 [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded
            [&_pre]:bg-background/50 [&_pre]:rounded-lg [&_pre]:p-2 [&_pre]:text-xs [&_pre]:overflow-x-auto
            [&_a]:text-primary [&_a]:no-underline [&_a:hover]:underline
            [&_hr]:hidden">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {cleanContent(msg.contentMd || '')}
            </ReactMarkdown>
          </div>
        )}
        {msg.citations.length > 0 && <CitationList citations={msg.citations} />}
        {msg.role === 'assistant' && hasValidStrategyJson(msg.contentMd) && (
          <ImplementButton messageContent={msg.contentMd!} />
        )}
      </div>
    </div>
  );
});

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
        <div className="space-y-3">
          <div className="w-10 h-10 mx-auto rounded-xl bg-primary/10 flex items-center justify-center">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="hsl(var(--primary))" strokeWidth="2">
              <path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z" />
              <path d="M10 21h4" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">Cerberus AI</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Ask me to build a strategy, analyze your portfolio, or deploy a bot.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} msg={msg} />
      ))}

      {isStreaming && streamingContent && (
        <div className="flex justify-start">
          <div className="max-w-[88%] rounded-xl rounded-bl-md px-3.5 py-2.5 text-sm bg-muted/80 text-foreground">
            <div className="cerberus-md prose prose-sm prose-invert max-w-none
              [&_p]:my-1 [&_ul]:my-1 [&_li]:my-0.5 [&_strong]:text-foreground [&_hr]:hidden">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {cleanContent(streamingContent)}
              </ReactMarkdown>
            </div>
            <span className="inline-block w-1.5 h-4 bg-primary/60 animate-pulse ml-0.5" />
          </div>
        </div>
      )}

      {isStreaming && !streamingContent && (
        <div className="flex justify-start">
          <div className="rounded-xl rounded-bl-md px-3.5 py-2.5 bg-muted/80">
            <div className="flex space-x-1.5">
              <span className="w-2 h-2 rounded-full bg-primary/50 animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 rounded-full bg-primary/50 animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 rounded-full bg-primary/50 animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
