"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { RefreshCw, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { GeneratingLoader } from "@/components/ui/generating-loader";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { ApiError } from "@/lib/api-client";
import {
  useDeleteRestoration,
  useRerunRestoration,
  useRestoration,
} from "@/lib/queries";
import { RestorationThumb } from "./restoration-thumb";
import { RestorationForm } from "./restoration-form";
import type { Restoration } from "@deoldify-archive-colorizer/shared";

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[8rem_minmax(0,1fr)] gap-3 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0 break-all font-mono text-xs">{value}</span>
    </div>
  );
}

function CompareView({ r }: { r: Restoration }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <figure className="space-y-2">
        <figcaption className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Original (B&amp;W)
        </figcaption>
        <div className="overflow-hidden rounded-lg border bg-muted/30">
          <RestorationThumb
            assetId={r.asset_id}
            target="source"
            mediaType="image"
            alt="Original black-and-white master"
            className="aspect-video w-full"
          />
        </div>
      </figure>
      <figure className="space-y-2">
        <figcaption className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Restored (color)
        </figcaption>
        <div className="overflow-hidden rounded-lg border bg-muted/30">
          {r.status === "completed" ? (
            <RestorationThumb
              assetId={r.asset_id}
              target="rendition"
              mediaType={r.media_type}
              alt="Colorized restored rendition"
              className="aspect-video w-full"
            />
          ) : (
            <div className="flex aspect-video w-full items-center justify-center p-4 text-center text-sm text-muted-foreground">
              Colorization failed — re-colorize to try again.
            </div>
          )}
        </div>
      </figure>
    </div>
  );
}

export function RestorationDetail({ assetId }: { assetId: string }) {
  const router = useRouter();
  const { data: r, isLoading, error, refetch } = useRestoration(assetId);
  const rerun = useRerunRestoration();
  const del = useDeleteRestoration();
  const [rerunOpen, setRerunOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  if (isLoading) {
    return <Skeleton className="h-96 w-full" />;
  }
  if (error || !r) {
    return (
      <ErrorState
        error={error ?? new Error("Restoration not found")}
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold">{r.asset_id}</h2>
          {r.status === "completed" ? (
            <Badge variant="secondary">Completed</Badge>
          ) : (
            <Badge variant="destructive">Failed</Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setRerunOpen(true)}
            disabled={rerun.isPending}
          >
            <RefreshCw aria-hidden className="h-3.5 w-3.5" />
            Re-colorize
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setDeleteOpen(true)}
            className="text-destructive"
            disabled={del.isPending}
          >
            <Trash2 aria-hidden className="h-3.5 w-3.5" />
            Delete
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-5">
          <CompareView r={r} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="border-b border-border py-4 px-5">
          <CardTitle className="card-title">Provenance</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 p-5">
          <MetaRow label="Source key" value={r.source_key} />
          <MetaRow label="Rendition key" value={r.rendition_key} />
          <MetaRow label="Model" value={r.model_version} />
          <MetaRow label="Variant" value={r.params.model_variant} />
          <MetaRow label="Render factor" value={String(r.render_factor)} />
          <MetaRow
            label="Restore pass"
            value={`denoise=${r.params.denoise} sharpen=${r.params.sharpen}`}
          />
          <MetaRow label="Device" value={r.device} />
          <MetaRow label="Created" value={r.created_at} />
          <MetaRow label="Updated" value={r.updated_at} />
          {r.error && <MetaRow label="Error" value={r.error} />}
        </CardContent>
      </Card>

      <Dialog open={rerunOpen} onOpenChange={setRerunOpen}>
        <DialogContent className="max-h-[85svh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Re-colorize with new params</DialogTitle>
          </DialogHeader>
          {rerun.isPending ? (
            <div className="flex flex-col items-center gap-3 py-10">
              <GeneratingLoader size="lg" label="Re-colorizing..." />
            </div>
          ) : (
            <RestorationForm
              mode="rerun"
              fixedSourceKey={r.source_key}
              initialParams={r.params}
              submitLabel="Re-colorize"
              submitting={rerun.isPending}
              onSubmit={(values) =>
                rerun.mutate(
                  {
                    assetId: r.asset_id,
                    params: {
                      model_variant: values.model_variant,
                      render_quality: values.render_quality,
                      denoise: values.denoise,
                      sharpen: values.sharpen,
                    },
                  },
                  {
                    onSuccess: () => {
                      toast.success("Re-colorized");
                      setRerunOpen(false);
                    },
                    onError: (err) =>
                      toast.error(
                        err instanceof ApiError
                          ? err.message
                          : "Re-colorize failed"
                      ),
                  }
                )
              }
            />
          )}
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this restoration?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes only the restored rendition and its metadata. The
              original B&amp;W master under <code>archive/originals/</code> is
              kept.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={del.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={del.isPending}
              onClick={() =>
                del.mutate(r.asset_id, {
                  onSuccess: () => {
                    toast.success("Restoration deleted");
                    router.push("/restorations");
                  },
                  onError: (err) =>
                    toast.error(
                      err instanceof ApiError ? err.message : "Delete failed"
                    ),
                })
              }
            >
              {del.isPending ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
