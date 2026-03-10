'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { parseStrategySpec, specToBuilderFields } from '@/lib/strategy-spec';
import { useStrategyBuilderStore } from '@/stores/strategy-builder-store';

interface ImplementButtonProps {
  messageContent: string;
}

export function ImplementButton({ messageContent }: ImplementButtonProps) {
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const setPendingSpec = useStrategyBuilderStore((s) => s.setPendingSpec);

  const handleClick = useCallback(() => {
    setError(null);
    const result = parseStrategySpec(messageContent);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    const fields = specToBuilderFields(result.spec);
    setPendingSpec(fields);
    router.push('/');
  }, [messageContent, setPendingSpec, router]);

  return (
    <div className="mt-2">
      <button
        onClick={handleClick}
        className="text-xs font-medium px-3 py-1.5 rounded-md bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20 transition-colors"
      >
        Implement strategy
      </button>
      {error && (
        <p className="text-xs text-red-400 mt-1">{error}</p>
      )}
    </div>
  );
}
