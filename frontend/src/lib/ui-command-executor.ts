import { validateUICommand, type UICommand } from '@/types/ui-commands';
import { useCerberusStore } from '@/stores/cerberus-store';
import { useUIContextStore } from '@/stores/ui-context-store';

export function executeUICommands(commands: UICommand[]): void {
  for (const cmd of commands) {
    if (!validateUICommand(cmd)) {
      console.warn('[UICmd] Rejected invalid command:', cmd.action);
      continue;
    }
    executeCommand(cmd);
  }
}

function executeCommand(cmd: UICommand): void {
  const cerberus = useCerberusStore.getState();

  switch (cmd.action) {
    case 'open_panel':
      cerberus.openCerberus();
      if (cmd.panel) {
        const tabMap: Record<string, 'chat' | 'strategy' | 'portfolio' | 'bots' | 'research'> = {
          chat: 'chat', strategy_builder: 'strategy', strategy: 'strategy',
          portfolio_analysis: 'portfolio', portfolio: 'portfolio',
          bot_control: 'bots', bots: 'bots', research: 'research',
        };
        const tab = tabMap[cmd.panel];
        if (tab) cerberus.setActiveTab(tab);
      }
      break;

    case 'switch_tab':
      if (cmd.tab) cerberus.setActiveTab(cmd.tab as any);
      break;

    case 'navigate':
      if (cmd.route && cmd.route.startsWith('/')) {
        window.location.href = cmd.route;
      }
      break;

    case 'show_toast':
      // Use browser notification or custom toast system
      console.log(`[Toast:${cmd.toastType || 'info'}] ${cmd.message}`);
      break;

    case 'focus_symbol':
      if (cmd.symbol) {
        useUIContextStore.getState().updateSelectedSymbol(cmd.symbol);
      }
      break;

    case 'highlight_component':
      if (cmd.componentId) {
        const el = document.querySelector(`[data-component-id="${cmd.componentId}"]`);
        if (el) {
          el.classList.add('cerberus-highlight');
          setTimeout(() => el.classList.remove('cerberus-highlight'), cmd.durationMs || 2500);
        }
      }
      break;

    case 'open_confirmation_modal':
      if (cmd.proposalId) {
        // Trigger proposal display
        cerberus.openCerberus();
      }
      break;

    default:
      console.log('[UICmd] Unhandled:', cmd.action);
  }
}
