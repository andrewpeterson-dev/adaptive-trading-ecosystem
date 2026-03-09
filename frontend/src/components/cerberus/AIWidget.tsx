'use client';

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useCerberusStore } from '@/stores/cerberus-store';
import { ChatPanel } from './ChatPanel';
import { StrategyBuilder } from './StrategyBuilder';
import { PortfolioAnalysis } from './PortfolioAnalysis';
import { BotControlPanel } from './BotControlPanel';
import { ResearchPanel } from './ResearchPanel';

const TABS = [
  { id: 'chat' as const, label: 'Chat' },
  { id: 'strategy' as const, label: 'Strategy' },
  { id: 'portfolio' as const, label: 'Portfolio' },
  { id: 'bots' as const, label: 'Bots' },
  { id: 'research' as const, label: 'Research' },
];

export function AIWidget() {
  const { isOpen, activeTab, setActiveTab, openCerberus, closeCerberus } = useCerberusStore();
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const bubbleRef = useRef<HTMLDivElement>(null);

  // Load saved position
  useEffect(() => {
    const saved = localStorage.getItem('cerberus_position');
    if (saved) {
      try { setPosition(JSON.parse(saved)); } catch { /* ignore */ }
    }
  }, []);

  // Save position on change
  useEffect(() => {
    if (position.x !== 0 || position.y !== 0) {
      localStorage.setItem('cerberus_position', JSON.stringify(position));
    }
  }, [position]);

  return (
    <>
      {/* Floating Bubble */}
      <AnimatePresence>
        {!isOpen && (
          <motion.div
            ref={bubbleRef}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            drag
            dragMomentum={false}
            onDragStart={() => setIsDragging(true)}
            onDragEnd={(_, info) => {
              setIsDragging(false);
              setPosition(prev => ({
                x: prev.x + info.offset.x,
                y: prev.y + info.offset.y,
              }));
            }}
            onClick={() => { if (!isDragging) openCerberus(); }}
            className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full cursor-pointer
                       bg-primary/90 backdrop-blur-md shadow-lg shadow-primary/25
                       flex items-center justify-center
                       hover:scale-110 transition-transform"
            style={{ x: position.x, y: position.y }}
            whileHover={{ boxShadow: '0 0 20px hsl(var(--primary) / 0.4)' }}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
              <path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z" />
              <path d="M10 21h4" />
            </svg>
            {/* Pulse indicator */}
            <span className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-400 animate-pulse" />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Expanded Panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ x: '100%', opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: '100%', opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed top-0 right-0 z-50 h-full w-full sm:w-[420px]
                       bg-background/95 backdrop-blur-xl border-l border-border
                       shadow-2xl flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h2 className="text-sm font-semibold text-foreground">Cerberus</h2>
              <button
                onClick={closeCerberus}
                className="p-1.5 rounded-md hover:bg-muted transition-colors text-muted-foreground"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Tab Bar */}
            <div className="flex border-b border-border overflow-x-auto">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex-1 min-w-0 px-2 py-2.5 text-xs font-medium transition-colors
                    ${activeTab === tab.id
                      ? 'text-primary border-b-2 border-primary'
                      : 'text-muted-foreground hover:text-foreground'
                    }`}
                >
                  <span className="block truncate">{tab.label}</span>
                </button>
              ))}
            </div>

            {/* Tab Content */}
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
