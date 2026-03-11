"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Newspaper } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDateTime, formatRelativeTime } from "@/lib/trading/format";
import type { NewsArticle } from "@/types/trading";

interface SymbolNewsFeedProps {
  symbol: string;
  limit?: number;
  compact?: boolean;
  articles?: NewsArticle[];
  loading?: boolean;
}

export function SymbolNewsFeed({
  symbol,
  limit = 6,
  compact = false,
  articles,
  loading,
}: SymbolNewsFeedProps) {
  const [fetchedArticles, setFetchedArticles] = useState<NewsArticle[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (articles) {
      setFetchedArticles([]);
      setIsLoading(false);
      return;
    }

    let cancelled = false;

    async function loadNews() {
      setIsLoading(true);
      try {
        const data = await apiFetch<{ articles: NewsArticle[] }>(
          `/api/trading/news?symbol=${encodeURIComponent(symbol)}&limit=${limit}`,
        );
        if (!cancelled) setFetchedArticles(data.articles || []);
      } catch {
        if (!cancelled) setFetchedArticles([]);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void loadNews();
    return () => {
      cancelled = true;
    };
  }, [articles, limit, symbol]);

  const resolvedArticles = articles ?? fetchedArticles;
  const resolvedLoading = loading ?? isLoading;

  if (resolvedLoading) {
    return (
      <div className="rounded-[18px] border border-border/70 bg-muted/20 px-4 py-4 text-sm text-muted-foreground">
        Loading news for {symbol}...
      </div>
    );
  }

  if (resolvedArticles.length === 0) {
    return (
      <EmptyState
        icon={<Newspaper className="h-5 w-5 text-muted-foreground" />}
        title="No current headlines"
        description={`We could not load fresh news for ${symbol}. Try refresh or open the Research tab for broader market context.`}
        className="border border-dashed border-border/70 bg-muted/15"
      />
    );
  }

  return (
    <div className="space-y-3">
      {resolvedArticles.map((article) => (
        <article
          key={article.url || article.title}
          className="rounded-[18px] border border-border/70 bg-background/70 px-4 py-4"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                {article.source || "Market News"} · {formatRelativeTime(article.published_at)}
              </p>
              <h3 className="mt-1 text-sm font-semibold text-foreground">{article.title}</h3>
            </div>
            {article.url && (
              <a
                href={article.url}
                target="_blank"
                rel="noreferrer"
                className="rounded-full border border-border/70 bg-muted/25 p-2 text-muted-foreground transition-colors hover:text-foreground"
                aria-label={`Open article: ${article.title}`}
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
          </div>
          {!compact && article.summary && (
            <p className="mt-3 text-sm leading-6 text-muted-foreground">{article.summary}</p>
          )}
          <p className="mt-3 text-[11px] text-muted-foreground">
            {formatDateTime(article.published_at)}
          </p>
        </article>
      ))}
    </div>
  );
}
