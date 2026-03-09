'use client';

import type { Citation } from '@/types/copilot';

interface CitationListProps {
  citations: Citation[];
}

export function CitationList({ citations }: CitationListProps) {
  if (citations.length === 0) return null;

  return (
    <div className="mt-2 pt-2 border-t border-border/50">
      <p className="text-xs font-medium text-muted-foreground mb-1">Sources</p>
      <ul className="space-y-0.5">
        {citations.map((cite, i) => (
          <li key={i} className="text-xs text-muted-foreground">
            {cite.url ? (
              <a
                href={cite.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                [{i + 1}] {cite.title}
              </a>
            ) : (
              <span>[{i + 1}] {cite.title}</span>
            )}
            {cite.snippet && (
              <span className="block ml-4 text-muted-foreground/70 truncate">{cite.snippet}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
