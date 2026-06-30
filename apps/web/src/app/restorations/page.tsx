import Link from "next/link";
import { Palette } from "lucide-react";

import { Button } from "@/components/ui/button";
import { RestorationLibrary } from "@/components/restorations/restoration-library";

export default function RestorationsPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
        <div className="min-w-0">
          <h1 className="page-title">Restorations</h1>
          <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
            Colorized renditions scoped to <code>archive/restored/</code>, paired
            with their original B&amp;W masters. Both are retained in B2.
          </p>
        </div>
        <Button asChild size="sm" className="h-8 shrink-0">
          <Link href="/restorations/new">
            <Palette aria-hidden className="h-3.5 w-3.5" />
            New restoration
          </Link>
        </Button>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <RestorationLibrary />
      </div>
    </div>
  );
}
