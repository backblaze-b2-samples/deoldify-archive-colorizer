import { CreateRestoration } from "@/components/restorations/create-restoration";

export default async function NewRestorationPage({
  searchParams,
}: {
  // `?source=<b2 key>` pre-selects an original in the picker — set by the
  // "Colorize" CTA on the upload page so ingest chains straight into restore.
  searchParams: Promise<{ source?: string }>;
}) {
  const { source } = await searchParams;
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">New Restoration</h1>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground text-pretty">
          Pick an ingested black-and-white master and colorization parameters.
          Submitting runs DeOldify locally and stores the restored rendition plus
          provenance metadata in B2.
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2 max-w-2xl">
        <CreateRestoration initialSourceKey={source} />
      </div>
    </div>
  );
}
