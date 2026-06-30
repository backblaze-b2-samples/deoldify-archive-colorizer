"use client";

import Link from "next/link";
import { Palette, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useRestorations } from "@/lib/queries";
import { RestorationThumb } from "./restoration-thumb";
import type { Restoration } from "@deoldify-archive-colorizer/shared";

function StatusBadge({ status }: { status: Restoration["status"] }) {
  return status === "completed" ? (
    <Badge variant="secondary">Completed</Badge>
  ) : (
    <Badge variant="destructive">Failed</Badge>
  );
}

function RestorationCard({ r }: { r: Restoration }) {
  return (
    <Link
      href={`/restorations/${r.asset_id}`}
      className="group block overflow-hidden rounded-lg border border-border transition-colors hover:border-primary"
    >
      <div className="grid grid-cols-2 gap-px bg-border">
        <div className="bg-muted/30">
          <RestorationThumb
            assetId={r.asset_id}
            target="source"
            mediaType="image"
            alt={`Original of ${r.asset_id}`}
            className="aspect-square w-full"
          />
        </div>
        <div className="bg-muted/30">
          {r.status === "completed" ? (
            <RestorationThumb
              assetId={r.asset_id}
              target="rendition"
              mediaType={r.media_type}
              alt={`Restored ${r.asset_id}`}
              className="aspect-square w-full"
            />
          ) : (
            <div className="flex aspect-square w-full items-center justify-center text-xs text-muted-foreground">
              No rendition
            </div>
          )}
        </div>
      </div>
      <div className="space-y-1.5 p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-medium">{r.asset_id}</span>
          <StatusBadge status={r.status} />
        </div>
        <p className="truncate text-xs text-muted-foreground">
          {r.params.model_variant} · render factor {r.render_factor} ·{" "}
          {r.device}
        </p>
      </div>
    </Link>
  );
}

export function RestorationLibrary() {
  const { data: restorations = [], isLoading, isFetching, error, refetch } =
    useRestorations();

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4 space-y-0">
        <CardTitle className="card-title">
          Restoration Library (archive/restored/)
        </CardTitle>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          className="h-7 shrink-0 text-xs"
          disabled={isFetching}
          aria-label={isFetching ? "Refreshing" : "Refresh restorations"}
        >
          <RefreshCw
            aria-hidden
            className={`mr-1 h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
      </CardHeader>
      <CardContent className="p-4" aria-busy={isLoading || isFetching}>
        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-56 w-full" />
            ))}
          </div>
        ) : error ? (
          <ErrorState
            error={error}
            title="Couldn't load restorations"
            onRetry={() => refetch()}
          />
        ) : restorations.length === 0 ? (
          <EmptyState
            icon={Palette}
            title="No restorations yet"
            description="Colorize an ingested B&W original to create your first restoration."
            action={
              <Button asChild size="sm">
                <Link href="/restorations/new">
                  <Palette aria-hidden className="h-3.5 w-3.5" />
                  New restoration
                </Link>
              </Button>
            }
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {restorations.map((r) => (
              <RestorationCard key={r.asset_id} r={r} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
