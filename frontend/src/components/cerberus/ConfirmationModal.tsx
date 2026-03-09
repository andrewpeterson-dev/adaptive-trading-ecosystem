'use client';

import { useState } from 'react';
import { useCerberusStore } from '@/stores/cerberus-store';
import { confirmTrade, executeTrade } from '@/lib/cerberus-api';

export function ConfirmationModal() {
  const { pendingProposal, setPendingProposal } = useCerberusStore();
  const [isConfirming, setIsConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!pendingProposal) return null;

  const handleConfirm = async () => {
    setIsConfirming(true);
    setError(null);
    try {
      const { confirmationToken } = await confirmTrade(pendingProposal.id);
      await executeTrade(pendingProposal.id, confirmationToken);
      setPendingProposal(null);
    } catch (e: any) {
      setError(e.message || 'Failed to execute trade');
    } finally {
      setIsConfirming(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-background border border-border rounded-xl shadow-2xl max-w-md w-full mx-4 p-5 space-y-4">
        <h3 className="text-base font-semibold text-foreground">Confirm Trade</h3>

        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Symbol</span>
            <span className="font-medium text-foreground">{pendingProposal.symbol}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Side</span>
            <span className={`font-medium ${pendingProposal.side === 'buy' ? 'text-emerald-500' : 'text-red-500'}`}>
              {pendingProposal.side.toUpperCase()}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Quantity</span>
            <span className="font-medium text-foreground">{pendingProposal.quantity}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Type</span>
            <span className="font-medium text-foreground">{pendingProposal.orderType}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Mode</span>
            <span className={`font-medium ${pendingProposal.paperOrLive === 'live' ? 'text-red-400' : 'text-emerald-400'}`}>
              {pendingProposal.paperOrLive.toUpperCase()}
            </span>
          </div>
        </div>

        {pendingProposal.paperOrLive === 'live' && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-2.5 text-xs text-red-400">
            This is a LIVE trade. Real money will be used.
          </div>
        )}

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-2.5 text-xs text-red-400">
            {error}
          </div>
        )}

        <div className="flex gap-2">
          <button
            onClick={() => setPendingProposal(null)}
            className="flex-1 rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={isConfirming}
            className="flex-1 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {isConfirming ? 'Executing...' : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  );
}
