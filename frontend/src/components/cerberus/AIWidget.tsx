'use client';

import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  Bot,
  BrainCircuit,
  FolderSearch2,
  MessageSquareText,
  RefreshCw,
  Wallet,
  X,
} from 'lucide-react';
import { useTradingMode } from '@/hooks/useTradingMode';
import {
  useCerberusWorkspaceStatus,
  type ConnectedDataStatus,
} from '@/hooks/useCerberusWorkspaceStatus';
import { getThreadMessages } from '@/lib/cerberus-api';
import { useCerberusStore } from '@/stores/cerberus-store';
import { useShallow } from 'zustand/react/shallow';
import { useUIContextStore } from '@/stores/ui-context-store';
import dynamic from 'next/dynamic';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

const ChatPanel = dynamic(() => import('./ChatPanel').then((m) => m.ChatPanel), { ssr: false });
const StrategyBuilder = dynamic(() => import('./StrategyBuilder').then((m) => m.StrategyBuilder), { ssr: false });
const PortfolioAnalysis = dynamic(() => import('./PortfolioAnalysis').then((m) => m.PortfolioAnalysis), { ssr: false });
const BotControlPanel = dynamic(() => import('./BotControlPanel').then((m) => m.BotControlPanel), { ssr: false });
const ResearchPanel = dynamic(() => import('./ResearchPanel').then((m) => m.ResearchPanel), { ssr: false });

const TABS = [
  { id: 'chat' as const, label: 'Chat', icon: MessageSquareText },
  { id: 'strategy' as const, label: 'Strategy', icon: BrainCircuit },
  { id: 'portfolio' as const, label: 'Portfolio', icon: Wallet },
  { id: 'bots' as const, label: 'Bots', icon: Bot },
  { id: 'research' as const, label: 'Research', icon: FolderSearch2 },
];

const MODE_BY_TAB = {
  chat: 'chat',
  strategy: 'strategy',
  portfolio: 'portfolio',
  bots: 'bot_control',
  research: 'research',
} as const;

const BUBBLE_SIZE = 56;
const MOBILE_BREAKPOINT = 640;
const MOBILE_INSET = 16;
const DESKTOP_INSET = 24;
const VIEWPORT_MARGIN = 16;

function stateBadgeClass(state: ConnectedDataStatus['state']): string {
  if (state === 'connected') {
    return 'border-emerald-500/25 bg-emerald-500/12 text-emerald-300';
  }
  if (state === 'error') {
    return 'border-red-500/25 bg-red-500/12 text-red-200';
  }
  return 'border-amber-500/25 bg-amber-500/12 text-amber-300';
}

function stateBadgeLabel(state: ConnectedDataStatus['state']): string {
  if (state === 'connected') return 'Connected';
  if (state === 'error') return 'Error';
  return 'Not Connected';
}

function clampBubblePosition(position: { x: number; y: number }) {
  if (typeof window === 'undefined') {
    return position;
  }

  const inset =
    window.innerWidth < MOBILE_BREAKPOINT ? MOBILE_INSET : DESKTOP_INSET;
  const minX = VIEWPORT_MARGIN - (window.innerWidth - inset - BUBBLE_SIZE);
  const maxX = inset - VIEWPORT_MARGIN;
  const minY = VIEWPORT_MARGIN - (window.innerHeight - inset - BUBBLE_SIZE);
  const maxY = inset - VIEWPORT_MARGIN;

  return {
    x: Math.min(maxX, Math.max(minX, position.x)),
    y: Math.min(maxY, Math.max(minY, position.y)),
  };
}

export function AIWidget() {
  const { isOpen, activeTab, activeThreadId, messages } = useCerberusStore(
    useShallow((s) => ({
      isOpen: s.isOpen,
      activeTab: s.activeTab,
      activeThreadId: s.activeThreadId,
      messages: s.messages,
    }))
  );
  const setActiveTab = useCerberusStore((s) => s.setActiveTab);
  const setMode = useCerberusStore((s) => s.setMode);
  const openCerberus = useCerberusStore((s) => s.openCerberus);
  const closeCerberus = useCerberusStore((s) => s.closeCerberus);
  const setMessages = useCerberusStore((s) => s.setMessages);
  const pageContext = useUIContextStore((s) => s.pageContext);
  const { mode } = useTradingMode();
  const { status, loading, refresh } = useCerberusWorkspaceStatus(mode);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const bubbleRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const saved = localStorage.getItem('cerberus_position');
    if (saved) {
      try {
        setPosition(clampBubblePosition(JSON.parse(saved)));
      } catch {
        // ignore invalid local storage
      }
    }
  }, []);

  useEffect(() => {
    if (position.x !== 0 || position.y !== 0) {
      localStorage.setItem('cerberus_position', JSON.stringify(position));
    }
  }, [position]);

  useEffect(() => {
    const handleResize = () => {
      setPosition((current) => clampBubblePosition(current));
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    if (isOpen && activeThreadId && messages.length === 0) {
      getThreadMessages(activeThreadId)
        .then((fetched) => {
          if (fetched && fetched.length > 0) {
            setMessages(fetched);
          }
        })
        .catch(() => {
          // new session starts fresh
        });
    }
  }, [isOpen, activeThreadId, messages.length, setMessages]);

  const handleTabChange = (tabId: (typeof TABS)[number]['id']) => {
    setActiveTab(tabId);
    setMode(MODE_BY_TAB[tabId]);
  };

  return (
    <>
      <AnimatePresence mode="wait">
        {!isOpen && (
          <TooltipProvider delayDuration={300}>
            <Tooltip>
              <TooltipTrigger asChild>
                <motion.div
                  key="cerberus-bubble"
                  ref={bubbleRef}
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0, opacity: 0 }}
                  drag
                  dragMomentum={false}
                  onDragStart={() => setIsDragging(true)}
                  onDragEnd={(_, info) => {
                    setIsDragging(false);
                    setPosition((prev) =>
                      clampBubblePosition({
                        x: prev.x + info.offset.x,
                        y: prev.y + info.offset.y,
                      })
                    );
                  }}
                  onClick={() => {
                    if (!isDragging) openCerberus();
                  }}
                  className="animate-scale-in fixed bottom-24 right-4 z-50 flex h-14 w-14 touch-none cursor-pointer items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary/70 shadow-lg shadow-primary/30 transition-transform hover:scale-110 active:scale-95 sm:bottom-6 sm:right-6 lg:bottom-6"
                  style={{ x: position.x, y: position.y }}
                >
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z" />
                    <path d="M10 21h4" />
                  </svg>
                  <span className="absolute -right-0.5 -top-0.5 h-3 w-3 animate-pulse rounded-full bg-emerald-400 ring-2 ring-background" />
                </motion.div>
              </TooltipTrigger>
              <TooltipContent side="left">Ask Cerberus</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {isOpen && (
          <motion.div
            key="cerberus-panel"
            initial={{ x: '100%', opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: '100%', opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed inset-0 z-50 flex h-[100dvh] w-full min-w-0 flex-col border-l border-border/50 bg-background/95 shadow-2xl shadow-black/20 backdrop-blur-xl sm:left-auto sm:w-[480px]"
          >
            <div className="max-h-[40vh] overflow-y-auto border-b border-border/50 bg-gradient-to-r from-primary/6 via-transparent to-transparent px-4 py-4 sm:max-h-[45vh] sm:px-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/15">
                      <BrainCircuit className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <h2 className="text-sm font-semibold leading-none text-foreground">Cerberus</h2>
                      <p className="mt-1 text-[10px] text-muted-foreground">AI trading operator</p>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span
                      className={`rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${
                        status?.livePermission === 'enabled'
                          ? 'border-emerald-500/25 bg-emerald-500/12 text-emerald-300'
                          : status?.livePermission === 'blocked'
                            ? 'border-red-500/25 bg-red-500/12 text-red-200'
                            : 'border-amber-500/25 bg-amber-500/12 text-amber-300'
                      }`}
                    >
                      LIVE {status?.livePermission === 'enabled' ? 'permission on' : status?.livePermission === 'blocked' ? 'blocked' : 'gated'}
                    </span>
                    <span
                      className={`rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${
                        status?.tradeProposalsEnabled
                          ? 'border-emerald-500/25 bg-emerald-500/12 text-emerald-300'
                          : 'border-border/70 bg-muted/45 text-muted-foreground'
                      }`}
                    >
                      {status?.tradeProposalsEnabled ? 'Trade proposals ready' : 'Trade proposals disabled'}
                    </span>
                  </div>
                </div>

                <button
                  onClick={closeCerberus}
                  className="app-button-icon h-9 w-9"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="app-inset mt-4 rounded-[22px] p-3">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="app-label">Connected Data</p>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      Cerberus should only ask for permission when a capability below is disconnected or erroring.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void refresh()}
                    className="rounded-full border border-border/60 bg-background/60 p-2 text-muted-foreground transition-colors hover:text-foreground"
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
                  </button>
                </div>

                <div className="mt-3 space-y-2">
                  {loading && (
                    <div className="space-y-2">
                      {[0, 1, 2, 3].map((index) => (
                        <div key={index} className="h-12 rounded-2xl border border-border/60 bg-background/50" />
                      ))}
                    </div>
                  )}

                  {!loading &&
                    status?.connectedData.map((item) => (
                      <div
                        key={item.key}
                        className="rounded-2xl border border-border/60 bg-background/60 px-3 py-2"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-foreground">{item.label}</p>
                            <p className="mt-1 text-[11px] leading-5 text-muted-foreground">
                              {item.detail}
                            </p>
                          </div>
                          <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${stateBadgeClass(item.state)}`}>
                            {stateBadgeLabel(item.state)}
                          </span>
                        </div>
                      </div>
                    ))}
                </div>
              </div>

              <div className="app-inset mt-3 rounded-[22px] p-3">
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-primary" />
                  <p className="app-label">State Table</p>
                </div>
                <div className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-2 text-[11px]">
                  <span className="text-muted-foreground">Mode</span>
                  <span className="font-medium text-foreground">{mode.toUpperCase()}</span>
                  <span className="text-muted-foreground">Selected symbol</span>
                  <span className="font-medium text-foreground">{pageContext.selectedSymbol ?? 'None'}</span>
                  <span className="text-muted-foreground">Broker</span>
                  <span className="font-medium text-foreground">{status?.activeBrokerLabel ?? 'Loading...'}</span>
                  <span className="text-muted-foreground">Market data</span>
                  <span className="font-medium text-foreground">{status?.marketDataLabel ?? 'Loading...'}</span>
                  <span className="text-muted-foreground">Bot registry</span>
                  <span className="font-medium text-foreground">{status?.botRegistryLabel ?? 'Loading...'}</span>
                  <span className="text-muted-foreground">Thread</span>
                  <span className="break-all font-medium text-foreground">{activeThreadId ?? 'New session'}</span>
                </div>
              </div>
            </div>

            <div className="flex overflow-x-auto border-b border-border/50 bg-muted/20">
              {TABS.map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => handleTabChange(tab.id)}
                    className={`relative min-w-[76px] flex-1 px-2 py-2.5 text-[11px] font-medium transition-all sm:min-w-0 ${
                      activeTab === tab.id
                        ? 'text-primary'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <span className="flex items-center justify-center gap-1.5">
                      <Icon className="h-3.5 w-3.5" />
                      <span className="truncate">{tab.label}</span>
                    </span>
                    {activeTab === tab.id && (
                      <motion.div
                        layoutId="cerberus-tab-indicator"
                        className="absolute bottom-0 left-1 right-1 h-0.5 rounded-full bg-primary"
                        transition={{ type: 'spring', damping: 30, stiffness: 300 }}
                      />
                    )}
                  </button>
                );
              })}
            </div>

            <div className="flex-1 overflow-hidden">
              {activeTab === 'chat' && <ChatPanel />}
              {activeTab === 'strategy' && <StrategyBuilder />}
              {activeTab === 'portfolio' && <PortfolioAnalysis />}
              {activeTab === 'bots' && <BotControlPanel />}
              {activeTab === 'research' && <ResearchPanel />}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
