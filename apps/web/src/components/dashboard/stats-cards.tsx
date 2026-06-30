"use client";

import { Palette, HardDrive, Images, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { useRestorationStats } from "@/lib/queries";

// Archival data-growth metrics. Visualizes the data-doubling story: a B&W
// archive becomes originals + restorations, both retained in B2.
export function StatsCards() {
  const { data: stats, isLoading, error, refetch } = useRestorationStats();

  if (error) {
    return (
      <Card>
        <CardContent className="p-0">
          <ErrorState error={error} onRetry={() => refetch()} />
        </CardContent>
      </Card>
    );
  }

  const cards = [
    {
      title: "Assets Restored",
      value: stats?.total_restorations ?? 0,
      icon: Palette,
    },
    {
      title: "Restorations Today",
      value: stats?.restorations_today ?? 0,
      icon: Images,
    },
    {
      title: "Archive Footprint",
      value: stats?.total_human ?? "0 B",
      icon: HardDrive,
    },
    {
      title: "Data Growth",
      value: stats ? `${stats.growth_ratio}x` : "1x",
      icon: TrendingUp,
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card, i) => (
        <Card
          key={card.title}
          className={`card-hover animate-fade-in-up stagger-${i + 1}`}
        >
          <CardHeader className="flex flex-row items-center justify-between pt-4 pb-2 px-4 space-y-0">
            <CardTitle className="text-xs font-semibold text-muted-foreground">
              {card.title}
            </CardTitle>
            <div className="stat-icon-wrap">
              <card.icon className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent className="pb-5 px-4">
            {isLoading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <div className="stat-value">{card.value}</div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
