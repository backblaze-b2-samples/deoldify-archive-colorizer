"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  createRestoration,
  deleteFile,
  deleteRestoration,
  getFiles,
  getFileStats,
  getPreviewUrl,
  getRestoration,
  getRestorations,
  getRestorationStats,
  getSourceOriginals,
  getUploadActivity,
  rerunRestoration,
} from "@/lib/api-client";
import type {
  FileMetadata,
  Restoration,
  RestorationParams,
} from "@deoldify-archive-colorizer/shared";

// Single source of truth for query keys. Keep these tightly scoped so that
// invalidating "files" doesn't blow away unrelated caches, and so an IDE
// "find usages" of `qk.files` reveals every consumer.
export const qk = {
  all: ["b2"] as const,
  files: (prefix?: string, limit?: number) =>
    [...qk.all, "files", prefix ?? "", limit ?? 100] as const,
  stats: () => [...qk.all, "stats"] as const,
  uploadActivity: (days: number) =>
    [...qk.all, "stats", "activity", days] as const,
  preview: (key: string) => [...qk.all, "preview", key] as const,
  restorations: () => [...qk.all, "restorations"] as const,
  restoration: (assetId: string) =>
    [...qk.all, "restorations", assetId] as const,
  restorationStats: () => [...qk.all, "restorations", "stats"] as const,
  sources: () => [...qk.all, "restorations", "sources"] as const,
};

export function useFiles(prefix = "", limit = 100) {
  return useQuery<FileMetadata[], ApiError>({
    queryKey: qk.files(prefix, limit),
    queryFn: () => getFiles(prefix, limit),
  });
}

export function useFileStats() {
  return useQuery({
    queryKey: qk.stats(),
    queryFn: getFileStats,
  });
}

export function useUploadActivity(days = 7) {
  return useQuery({
    queryKey: qk.uploadActivity(days),
    queryFn: () => getUploadActivity(days),
  });
}

// Presigned preview URL — only fetched when `enabled` is true (e.g., when
// the dialog opens for a specific file). Kept short-lived (60s) because
// the URL itself has a presigned expiry and is cheap to regenerate.
export function usePreviewUrl(key: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: qk.preview(key ?? ""),
    queryFn: () => getPreviewUrl(key as string),
    enabled: enabled && !!key,
    staleTime: 60_000,
  });
}

export function useDeleteFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fileKey: string) => deleteFile(fileKey),
    // After delete, blow away every cached file list + stats. Cheap and
    // correct — the dashboard re-fetches lazily as components remount.
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.all });
    },
  });
}

// --- Restorations ---

export function useRestorations() {
  return useQuery<Restoration[], ApiError>({
    queryKey: qk.restorations(),
    queryFn: getRestorations,
  });
}

export function useRestoration(assetId: string | undefined) {
  return useQuery<Restoration, ApiError>({
    queryKey: qk.restoration(assetId ?? ""),
    queryFn: () => getRestoration(assetId as string),
    enabled: !!assetId,
  });
}

export function useRestorationStats() {
  return useQuery({
    queryKey: qk.restorationStats(),
    queryFn: getRestorationStats,
  });
}

export function useSourceOriginals() {
  return useQuery({
    queryKey: qk.sources(),
    queryFn: getSourceOriginals,
  });
}

export function useCreateRestoration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      sourceKey,
      params,
    }: {
      sourceKey: string;
      params: RestorationParams;
    }) => createRestoration(sourceKey, params),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.all }),
  });
}

export function useRerunRestoration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      assetId,
      params,
    }: {
      assetId: string;
      params: RestorationParams;
    }) => rerunRestoration(assetId, params),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.all }),
  });
}

export function useDeleteRestoration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (assetId: string) => deleteRestoration(assetId),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.all }),
  });
}
