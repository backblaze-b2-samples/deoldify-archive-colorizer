"use client";

import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { BarChart3 } from "lucide-react";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useRestorationStats } from "@/lib/queries";

// Storage-growth chart: originals bytes vs restored bytes, side by side. This
// is the visual core of the data-doubling story — a B&W archive plus its
// colorized restorations both live in B2.
const chartConfig = {
  megabytes: {
    label: "MB stored",
    color: "var(--chart-1)",
  },
} satisfies ChartConfig;

function toMB(bytes: number) {
  return Math.round((bytes / (1024 * 1024)) * 10) / 10;
}

export function UploadChart() {
  const { data: stats, isLoading, error, refetch } = useRestorationStats();

  const data = useMemo(
    () =>
      stats
        ? [
            { kind: "Originals", megabytes: toMB(stats.originals_bytes) },
            { kind: "Restored", megabytes: toMB(stats.restored_bytes) },
          ]
        : [],
    [stats]
  );

  const hasData = stats && stats.total_bytes > 0;

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Storage Growth</CardTitle>
        <CardDescription className="text-xs">
          Originals vs restored renditions in B2
        </CardDescription>
        <CardAction className="text-right self-center">
          {isLoading ? (
            <Skeleton className="ml-auto h-6 w-16" />
          ) : (
            <>
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Total
              </div>
              <div className="text-lg font-semibold leading-tight tracking-tight tabular-nums">
                {stats?.total_human ?? "-"}
              </div>
            </>
          )}
        </CardAction>
      </CardHeader>
      <CardContent className="p-5">
        {isLoading ? (
          <Skeleton className="h-[240px] w-full" />
        ) : error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : !hasData ? (
          <EmptyState
            icon={BarChart3}
            title="No archive data yet"
            description="Ingest originals and run a colorization to see storage growth."
          />
        ) : (
          <ChartContainer config={chartConfig} className="h-[240px] w-full">
            <BarChart
              data={data}
              margin={{ top: 8, right: 4, left: -16, bottom: 0 }}
            >
              <defs>
                <linearGradient id="growth-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="0%"
                    stopColor="var(--color-megabytes)"
                    stopOpacity={0.95}
                  />
                  <stop
                    offset="100%"
                    stopColor="var(--color-megabytes)"
                    stopOpacity={0.55}
                  />
                </linearGradient>
              </defs>
              <CartesianGrid
                vertical={false}
                strokeDasharray="3 3"
                stroke="var(--border)"
              />
              <XAxis
                dataKey="kind"
                tickLine={false}
                axisLine={false}
                tickMargin={10}
                fontSize={11}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                tickMargin={6}
                fontSize={11}
                width={36}
              />
              <ChartTooltip
                cursor={{ fill: "var(--accent-subtle)" }}
                content={<ChartTooltipContent />}
              />
              <Bar
                dataKey="megabytes"
                fill="url(#growth-fill)"
                radius={[4, 4, 0, 0]}
                animationDuration={500}
                animationEasing="ease-out"
              />
            </BarChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
