export type FileStatus = "uploading" | "complete" | "error";

export interface FileMetadata {
  key: string;
  filename: string;
  folder: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
}

export interface FileMetadataDetail {
  filename: string;
  size_bytes: number;
  size_human: string;
  mime_type: string;
  extension: string;
  md5: string;
  sha256: string;
  uploaded_at: string;
  // Image-specific
  image_width: number | null;
  image_height: number | null;
  exif: Record<string, string> | null;
  // PDF-specific
  pdf_pages: number | null;
  pdf_author: string | null;
  pdf_title: string | null;
  // Audio/Video
  duration_seconds: number | null;
  codec: string | null;
  bitrate: number | null;
}

export interface FileUploadResponse {
  key: string;
  filename: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
  metadata: FileMetadataDetail | null;
}

export interface DailyUploadCount {
  date: string;
  uploads: number;
}

export interface UploadStats {
  total_files: number;
  total_size_bytes: number;
  total_size_human: string;
  uploads_today: number;
  total_downloads: number;
}

// --- Restoration (DeOldify colorizer primary entity) ---

export type ModelVariant = "artistic" | "stable";
export type RenderQuality = "draft" | "balanced" | "high";
export type RestorationStatus = "completed" | "failed";

export interface RestorationParams {
  model_variant: ModelVariant;
  render_quality: RenderQuality;
  denoise: boolean;
  sharpen: boolean;
}

export interface Restoration {
  asset_id: string;
  source_key: string;
  rendition_key: string;
  metadata_key: string;
  media_type: "image" | "video";
  params: RestorationParams;
  status: RestorationStatus;
  error: string | null;
  model_version: string;
  device: string;
  render_factor: number;
  source_size_bytes: number;
  rendition_size_bytes: number;
  created_at: string;
  updated_at: string;
}

export interface SourceOriginal {
  key: string;
  filename: string;
  size_human: string;
  content_type: string;
}

export interface RestorationStats {
  total_restorations: number;
  restorations_today: number;
  originals_bytes: number;
  originals_human: string;
  restored_bytes: number;
  restored_human: string;
  total_bytes: number;
  total_human: string;
  growth_ratio: number;
}
