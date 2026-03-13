import { useCerberusStore } from '@/stores/cerberus-store';
import type { StreamEvent, AssistantMessage } from '@/types/cerberus';
import { getWebSocketToken } from '@/lib/api/auth';
import { ApiError } from '@/lib/api/client';
import { getWebSocketOrigin } from '@/lib/websocket-url';

const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_RECONNECT_DELAY_MS = 1000;

export class CerberusWebSocket {
  private ws: WebSocket | null = null;
  private threadId: string;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private intentionalClose = false;

  constructor(threadId: string) {
    this.threadId = threadId;
  }

  connect(): void {
    this.intentionalClose = false;
    void this.openSocket();
  }

  private async openSocket(): Promise<void> {
    try {
      const { token } = await getWebSocketToken();
      const wsOrigin = getWebSocketOrigin();
      const wsUrl = `${wsOrigin}/api/ai/stream/${this.threadId}?token=${encodeURIComponent(token)}`;

      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        console.log('[CerberusWS] Connected', this.threadId);
      };

      this.ws.onmessage = (event) => {
        try {
          const data: StreamEvent = JSON.parse(event.data);
          this.handleEvent(data);
        } catch (e) {
          console.error('[CerberusWS] Parse error', e);
        }
      };

      this.ws.onclose = (event) => {
        console.log('[CerberusWS] Disconnected', event.code, event.reason);
        this.ws = null;

        if (this.intentionalClose) return;
        if (event.code === 1000 || event.code === 1001) return;

        this.scheduleReconnect();
      };

      this.ws.onerror = (error) => {
        console.error('[CerberusWS] Error', error);
        this.ws?.close();
      };
    } catch (error) {
      console.error('[CerberusWS] Failed to create websocket ticket', error);
      this.ws = null;

      if (this.intentionalClose) {
        return;
      }
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        useCerberusStore.getState().setStreaming(false);
        return;
      }
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.warn('[CerberusWS] Max reconnect attempts reached');
      const store = useCerberusStore.getState();
      store.setStreaming(false);
      return;
    }

    const delay = BASE_RECONNECT_DELAY_MS * 2 ** this.reconnectAttempts;
    this.reconnectAttempts++;
    console.log(`[CerberusWS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    this.reconnectTimeout = setTimeout(() => this.connect(), delay);
  }

  send(data: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  disconnect(): void {
    this.intentionalClose = true;
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
    this.ws?.close(1000, 'Client disconnect');
    this.ws = null;
  }

  private handleEvent(event: StreamEvent): void {
    const store = useCerberusStore.getState();

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
        console.error('[CerberusWS] Error event', event.data);
        break;

      case 'done':
        store.setStreaming(false);
        store.clearToolCalls();
        // Stream complete — close cleanly (no reconnect needed)
        this.intentionalClose = true;
        this.ws?.close(1000, 'Stream complete');
        break;
    }
  }
}
