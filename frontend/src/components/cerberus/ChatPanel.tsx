'use client';

import { useCallback } from 'react';
import { useCerberusStore } from '@/stores/cerberus-store';
import { useUIContextStore } from '@/stores/ui-context-store';
import { sendChatMessage } from '@/lib/cerberus-api';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';

export function ChatPanel() {
  const {
    messages, activeThreadId, isStreaming, streamingContent,
    mode, setActiveThread, addMessage, setStreaming,
    clearStreamContent,
  } = useCerberusStore();
  const { pageContext } = useUIContextStore();

  const handleSend = useCallback(async (text: string) => {
    if (!text.trim() || isStreaming) return;

    // Add user message immediately
    addMessage({
      id: `user-${Date.now()}`,
      role: 'user',
      contentMd: text,
      structuredJson: null,
      modelName: null,
      citations: [],
      toolCalls: [],
      createdAt: new Date().toISOString(),
    });

    setStreaming(true);
    clearStreamContent();

    try {
      const response = await sendChatMessage({
        threadId: activeThreadId || undefined,
        mode,
        message: text,
        pageContext,
      });

      if (!activeThreadId) {
        setActiveThread(response.threadId);
      }

      // Add assistant message from response
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
      console.error('Chat error:', error);
      addMessage({
        id: `error-${Date.now()}`,
        role: 'assistant',
        contentMd: 'Sorry, there was an error processing your request. Please try again.',
        structuredJson: null,
        modelName: null,
        citations: [],
        toolCalls: [],
        createdAt: new Date().toISOString(),
      });
    } finally {
      setStreaming(false);
    }
  }, [activeThreadId, mode, pageContext, isStreaming, addMessage, setStreaming, setActiveThread, clearStreamContent]);

  return (
    <div className="flex flex-col h-full">
      <MessageList messages={messages} streamingContent={streamingContent} isStreaming={isStreaming} />
      <MessageInput onSend={handleSend} isStreaming={isStreaming} />
    </div>
  );
}
