'use client';

import type { Citation } from '@/types/copilot';

interface CitationListProps {
  citations: Citation[];
}

export function CitationList({ citations }: CitationListProps) {
  if (citations.length === 0) return null;

  const internal = citations.filter(c => c.source === 'internal');
  const external = citations.filter(c => c.source === 'external');

  return (
    <div className="mt-2 pt-2 border-t border-border/50 space-y-1.5">
      {internal.length > 0 && (
        <div>
          <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Documents</span>
          {internal.map((c, i) => (
            <div key={i} className="flex items-start gap-1.5 mt-0.5">
              <span className="text-[10px] text-primary font-mono">[{i + 1}]</span>
              <span className="text-[11px] text-muted-foreground">
                {c.title}{c.pageNumber ? ` (p.${c.pageNumber})` : ''}
              </span>
            </div>
          ))}
        </div>
      )}

      {external.length > 0 && (
        <div>
          <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Sources</span>
          {external.map((c, i) => (
            <div key={i} className="flex items-start gap-1.5 mt-0.5">
              <span className="text-[10px] text-blue-400 font-mono">[{internal.length + i + 1}]</span>
              {c.url ? (
                <a
                  href={c.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] text-blue-400 hover:underline truncate max-w-[250px]"
                >
                  {c.title}
                </a>
              ) : (
                <span className="text-[11px] text-muted-foreground">{c.title}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
