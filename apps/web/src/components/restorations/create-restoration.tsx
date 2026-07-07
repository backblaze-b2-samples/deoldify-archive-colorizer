"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { GeneratingLoader } from "@/components/ui/generating-loader";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { Upload } from "lucide-react";
import { ApiError } from "@/lib/api-client";
import { useCreateRestoration, useSourceOriginals } from "@/lib/queries";
import { RestorationForm } from "./restoration-form";
import { ElapsedTimer } from "./elapsed-timer";

export function CreateRestoration({
  initialSourceKey,
}: {
  // Pre-selects a just-uploaded original (from /restorations/new?source=…).
  initialSourceKey?: string;
}) {
  const router = useRouter();
  const { data: sources = [], isLoading, error, refetch } = useSourceOriginals();
  const createMutation = useCreateRestoration();

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Colorize an original</CardTitle>
      </CardHeader>
      <CardContent className="p-5">
        {createMutation.isPending ? (
          <div className="flex flex-col items-center justify-center gap-4 py-16">
            <GeneratingLoader size="lg" label="Colorizing with DeOldify..." />
            <p className="max-w-sm text-center text-sm text-muted-foreground">
              Running the NoGAN model locally. A still takes seconds to a few
              minutes on CPU.
            </p>
            <ElapsedTimer className="text-sm text-muted-foreground" />
          </div>
        ) : isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-72" />
            <Skeleton className="h-10 w-72" />
          </div>
        ) : error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : sources.length === 0 ? (
          <EmptyState
            icon={Upload}
            title="No originals ingested yet"
            description="Ingest a black-and-white master before you can colorize it."
            action={
              <Button asChild size="sm">
                <Link href="/upload">
                  <Upload aria-hidden className="h-3.5 w-3.5" />
                  Ingest originals
                </Link>
              </Button>
            }
          />
        ) : (
          <RestorationForm
            mode="create"
            sources={sources}
            initialSourceKey={initialSourceKey}
            submitLabel="Colorize"
            submitting={createMutation.isPending}
            onSubmit={(values) =>
              createMutation.mutate(
                {
                  sourceKey: values.source_key,
                  params: {
                    model_variant: values.model_variant,
                    render_quality: values.render_quality,
                    denoise: values.denoise,
                    sharpen: values.sharpen,
                  },
                },
                {
                  onSuccess: (record) => {
                    if (record.status === "failed") {
                      toast.error(
                        `Colorization failed: ${record.error ?? "unknown error"}`
                      );
                    } else {
                      toast.success("Restoration created");
                    }
                    router.push(`/restorations/${record.asset_id}`);
                  },
                  onError: (err) => {
                    const detail =
                      err instanceof ApiError
                        ? err.message
                        : "Failed to create restoration";
                    toast.error(detail);
                  },
                }
              )
            }
          />
        )}
      </CardContent>
    </Card>
  );
}
