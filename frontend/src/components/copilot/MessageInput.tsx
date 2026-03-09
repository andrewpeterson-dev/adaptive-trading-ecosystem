'use client';

import { useState, useRef, useCallback } from 'react';

interface MessageInputProps {
  onSend: (message: string) => void;
  isStreaming: boolean;
}

export function MessageInput({ onSend, isStreaming }: MessageInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(() => {
    if (!input.trim() || isStreaming) return;
    onSend(input.trim());
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [input, isStreaming, onSend]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }, [handleSubmit]);

  const handleInput = useCallback(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
    }
  }, []);

  return (
    <div className="border-t border-border px-3 py-3">
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => { setInput(e.target.value); handleInput(); }}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your portfolio, strategies, or market..."
          rows={1}
          className="flex-1 resize-none rounded-lg border border-border bg-muted/50 px-3 py-2
                     text-sm text-foreground placeholder:text-muted-foreground
                     focus:outline-none focus:ring-1 focus:ring-primary/50
                     max-h-[120px]"
          disabled={isStreaming}
        />
        <button
          onClick={handleSubmit}
          disabled={!input.trim() || isStreaming}
          className="shrink-0 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground
                     hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed
                     transition-colors"
        >
          {isStreaming ? (
            <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" strokeDasharray="60" strokeDashoffset="20" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
