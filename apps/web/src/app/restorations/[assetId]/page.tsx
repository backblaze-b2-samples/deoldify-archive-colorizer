import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { RestorationDetail } from "@/components/restorations/restoration-detail";

export default async function RestorationDetailPage({
  params,
}: {
  params: Promise<{ assetId: string }>;
}) {
  const { assetId } = await params;
  return (
    <div className="space-y-6">
      <div className="animate-fade-in border-b border-border pb-5">
        <Link
          href="/restorations"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft aria-hidden className="h-3.5 w-3.5" />
          Back to library
        </Link>
        <h1 className="page-title mt-2">Restoration detail</h1>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
          Side-by-side original vs restored, provenance, and re-colorize / delete
          actions.
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <RestorationDetail assetId={assetId} />
      </div>
    </div>
  );
}
