'use client';

import { useCallback } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { useCerberusStore } from '@/stores/cerberus-store';
import { useUIContextStore } from '@/stores/ui-context-store';
import { sendChatMessage } from '@/lib/cerberus-api';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';

export function ChatPanel() {
  // Select only the slices we need — prevents re-render when unrelated store fields change
  const { messages, activeThreadId, isStreaming, streamingContent, mode } =
    useCerberusStore(useShallow((s) => ({
      messages: s.messages,
      activeThreadId: s.activeThreadId,
      isStreaming: s.isStreaming,
      streamingContent: s.streamingContent,
      mode: s.mode,
    })));
  // Stable action references don't need shallow — they never change
  const setActiveThread = useCerberusStore((s) => s.setActiveThread);
  const addMessage = useCerberusStore((s) => s.addMessage);
  const setStreaming = useCerberusStore((s) => s.setStreaming);
  const clearStreamContent = useCerberusStore((s) => s.clearStreamContent);
  const pageContext = useUIContextStore((s) => s.pageContext);

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
      const detail =
        error instanceof Error ? error.message : 'Unknown error';
      addMessage({
        id: `error-${Date.now()}`,
        role: 'system',
        contentMd: `Something went wrong: ${detail}`,
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
