import { useCopilotStore } from '@/stores/copilot-store';
import type { StreamEvent, AssistantMessage } from '@/types/copilot';

export class CopilotWebSocket {
  private ws: WebSocket | null = null;
  private threadId: string;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

  constructor(threadId: string) {
    this.threadId = threadId;
  }

  connect(): void {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    const wsUrl = `${protocol}//${host}:8000/api/ai/stream/${this.threadId}`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('[CopilotWS] Connected', this.threadId);
    };

    this.ws.onmessage = (event) => {
      try {
        const data: StreamEvent = JSON.parse(event.data);
        this.handleEvent(data);
      } catch (e) {
        console.error('[CopilotWS] Parse error', e);
      }
    };

    this.ws.onclose = () => {
      console.log('[CopilotWS] Disconnected');
      this.reconnectTimeout = setTimeout(() => this.connect(), 3000);
    };

    this.ws.onerror = (error) => {
      console.error('[CopilotWS] Error', error);
    };
  }

  send(data: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  disconnect(): void {
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
    this.ws?.close();
    this.ws = null;
  }

  private handleEvent(event: StreamEvent): void {
    const store = useCopilotStore.getState();

    switch (event.type) {
      case 'assistant.delta':
        if (typeof event.data === 'object' && event.data !== null && 'text' in event.data) {
          store.appendStreamContent((event.data as { text: string }).text);
        }
        break;

      case 'assistant.message':
        store.setStreaming(false);
        store.clearStreamContent();
        const msg = event.data as AssistantMessage;
        store.addMessage({
          id: msg.turnId,
          role: 'assistant',
          contentMd: msg.markdown,
          structuredJson: msg,
          modelName: null,
          citations: msg.citations,
          toolCalls: [],
          createdAt: new Date().toISOString(),
        });
        break;

      case 'tool.start':
        if (typeof event.data === 'object' && event.data !== null) {
          const d = event.data as { toolName: string; category?: string };
          store.addToolCall({
            toolName: d.toolName,
            category: (d.category || 'portfolio') as any,
            status: 'running',
          });
        }
        break;

      case 'tool.result':
        if (typeof event.data === 'object' && event.data !== null) {
          const d = event.data as { toolName: string; success?: boolean };
          store.updateToolCall(d.toolName, {
            status: d.success ? 'completed' : 'failed',
          });
        }
        break;

      case 'trade.proposal':
        store.setPendingProposal(event.data as any);
        break;

      case 'ui.command':
        // Handled by ui-command-executor
        break;

      case 'error':
        store.setStreaming(false);
        console.error('[CopilotWS] Error event', event.data);
        break;

      case 'done':
        store.setStreaming(false);
        store.clearToolCalls();
        break;
    }
  }
}
