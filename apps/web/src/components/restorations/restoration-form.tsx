"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import type {
  RestorationParams,
  SourceOriginal,
} from "@deoldify-archive-colorizer/shared";

// Every finite-valued field is a selector / switch (no free text). On the
// create form, defaults are surfaced as FormDescription guidance only — there
// is no autofill button. Mirrors settings-form.tsx.
const schema = z.object({
  source_key: z.string().min(1, "Pick a source original"),
  model_variant: z.enum(["artistic", "stable", "video"]),
  render_quality: z.enum(["draft", "balanced", "high"]),
  denoise: z.boolean(),
  sharpen: z.boolean(),
});

export type RestorationFormValues = z.infer<typeof schema>;

const CREATE_DEFAULTS: RestorationFormValues = {
  source_key: "",
  model_variant: "artistic",
  render_quality: "balanced",
  denoise: true,
  sharpen: false,
};

interface RestorationFormProps {
  // When provided, the form runs in "re-colorize" mode: source is fixed and
  // fields open pre-filled with the restoration's current params (no create
  // hints). Otherwise it's the create form with a source picker + default hints.
  mode: "create" | "rerun";
  sources?: SourceOriginal[];
  initialParams?: RestorationParams;
  fixedSourceKey?: string;
  submitting?: boolean;
  submitLabel: string;
  onSubmit: (values: RestorationFormValues) => void;
}

export function RestorationForm({
  mode,
  sources = [],
  initialParams,
  fixedSourceKey,
  submitting = false,
  submitLabel,
  onSubmit,
}: RestorationFormProps) {
  const isCreate = mode === "create";
  const form = useForm<RestorationFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      ...CREATE_DEFAULTS,
      ...(initialParams ?? {}),
      source_key: fixedSourceKey ?? "",
    },
  });

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        {isCreate && (
          <FormField
            control={form.control}
            name="source_key"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Source original</FormLabel>
                <Select onValueChange={field.onChange} value={field.value}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Choose an ingested B&W master" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {sources.map((s) => (
                      <SelectItem key={s.key} value={s.key}>
                        {s.filename} · {s.size_human}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormDescription>
                  Pick an ingested B&amp;W master from{" "}
                  <code>archive/originals/</code>. Ingest more on the Ingest page.
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        <FormField
          control={form.control}
          name="model_variant"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Model variant</FormLabel>
              <Select onValueChange={field.onChange} value={field.value}>
                <FormControl>
                  <SelectTrigger className="w-72">
                    <SelectValue />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="artistic">Artistic (image)</SelectItem>
                  <SelectItem value="stable">Stable (image)</SelectItem>
                  <SelectItem value="video">Video (clips)</SelectItem>
                </SelectContent>
              </Select>
              {isCreate && (
                <FormDescription>
                  Artistic is best for most archival stills.
                </FormDescription>
              )}
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="render_quality"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Render quality</FormLabel>
              <Select onValueChange={field.onChange} value={field.value}>
                <FormControl>
                  <SelectTrigger className="w-72">
                    <SelectValue />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="draft">Draft (render factor 21)</SelectItem>
                  <SelectItem value="balanced">
                    Balanced (render factor 30)
                  </SelectItem>
                  <SelectItem value="high">High (render factor 35)</SelectItem>
                </SelectContent>
              </Select>
              {isCreate && (
                <FormDescription>
                  Balanced is a good detail/speed tradeoff for a first run.
                </FormDescription>
              )}
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="denoise"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center justify-between rounded-md border border-border p-3">
              <div className="space-y-0.5">
                <FormLabel>Denoise</FormLabel>
                {isCreate && (
                  <FormDescription>
                    Knocks back scan grain on the colorized output. On by default.
                  </FormDescription>
                )}
              </div>
              <FormControl>
                <Switch checked={field.value} onCheckedChange={field.onChange} />
              </FormControl>
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="sharpen"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center justify-between rounded-md border border-border p-3">
              <div className="space-y-0.5">
                <FormLabel>Sharpen</FormLabel>
                {isCreate && (
                  <FormDescription>
                    Recovers edge detail with an unsharp mask. Off by default.
                  </FormDescription>
                )}
              </div>
              <FormControl>
                <Switch checked={field.value} onCheckedChange={field.onChange} />
              </FormControl>
            </FormItem>
          )}
        />

        <div className="flex items-center justify-end">
          <Button type="submit" disabled={submitting}>
            {submitting ? "Colorizing..." : submitLabel}
          </Button>
        </div>
      </form>
    </Form>
  );
}
