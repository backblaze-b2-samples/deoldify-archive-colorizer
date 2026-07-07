import Link from "next/link";
import { Palette, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { RecentUploadsTable } from "@/components/dashboard/recent-uploads-table";
import { UploadChart } from "@/components/dashboard/upload-chart";

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1.5">
            Archival data growth — originals plus colorized restorations, all in
            Backblaze B2.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Step 1 — ingest a B&W original. Kept as prominent as the colorize
              CTA so the first step is as discoverable as the last. */}
          <Button asChild size="sm" className="h-8">
            <Link href="/upload">
              <Upload className="h-3.5 w-3.5" />
              Ingest original
            </Link>
          </Button>
          {/* Step 2 — colorize an ingested original. */}
          <Button asChild size="sm" variant="outline" className="h-8">
            <Link href="/restorations/new">
              <Palette className="h-3.5 w-3.5" />
              New restoration
            </Link>
          </Button>
        </div>
      </div>
      <StatsCards />
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="animate-fade-in-up stagger-3">
          <UploadChart />
        </div>
        <div className="animate-fade-in-up stagger-4">
          <RecentUploadsTable />
        </div>
      </div>
    </div>
  );
}
