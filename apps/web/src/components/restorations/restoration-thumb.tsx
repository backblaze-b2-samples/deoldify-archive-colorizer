"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import { ImageOff } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { getRestorationPreviewUrl } from "@/lib/api-client";
import { qk } from "@/lib/queries";

interface RestorationThumbProps {
  assetId: string;
  // "rendition" (color) or "source" (B&W). Used for both the gallery thumbnail
  // and the side-by-side compare view on the detail page.
  target: "source" | "rendition";
  mediaType: "image" | "video";
  alt: string;
  className?: string;
}

// Fetches a presigned preview URL for one asset surface and renders it. The
// <img>/<video> actually paints (naturalWidth > 0 / decoded frame) so the
// gallery and compare view show real pixels, not placeholders.
export function RestorationThumb({
  assetId,
  target,
  mediaType,
  alt,
  className,
}: RestorationThumbProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: [...qk.restoration(assetId), "preview", target],
    queryFn: () => getRestorationPreviewUrl(assetId, target),
    staleTime: 60_000,
  });

  const url = data?.url;

  if (isLoading) {
    return <Skeleton className={className ?? "h-40 w-full"} />;
  }

  if (isError || !url) {
    return (
      <div
        className={`flex items-center justify-center bg-muted/40 text-muted-foreground ${
          className ?? "h-40 w-full"
        }`}
      >
        <ImageOff className="h-5 w-5" aria-hidden />
        <span className="sr-only">Preview unavailable</span>
      </div>
    );
  }

  if (mediaType === "video" && target === "rendition") {
    return (
      <video
        src={url}
        controls
        muted
        playsInline
        preload="metadata"
        className={className ?? "h-40 w-full object-contain"}
      />
    );
  }

  return (
    <div className={`relative ${className ?? "h-40 w-full"}`}>
      <Image
        src={url}
        alt={alt}
        fill
        sizes="(max-width: 768px) 100vw, 400px"
        className="object-contain"
        unoptimized
      />
    </div>
  );
}
