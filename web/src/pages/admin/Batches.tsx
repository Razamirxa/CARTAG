import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ChangeEvent, type FormEvent } from "react";
import { Alert, Badge, Button, Card, ConfirmButton, Empty, Field, Input, Loading, PageHeader, Textarea } from "../../components/ui";
import { ApiError, api, errorMessage, type Batch } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { MAX_BATCH_SIZE } from "../../lib/rules";

const KEY = ["admin", "batches"] as const;

interface BatchDetail {
  batch: Batch;
  byStatus: Record<string, number>;
  byStock: Record<string, number>;
  print: {
    version: number;
    modulesPerSide: number;
    mode: string;
    physicalMm: number;
    moduleMm: number;
    printable: boolean;
    /** Only when a design is chosen: the QR's own width and whether it is light on dark. */
    qrMm?: number;
    inverted?: boolean;
  } | null;
  sampleUrl: string | null;
  pdfParts: number;
}

/**
 * The three tag sizes the client chose (whole tag, in millimetres) and the QR size drawn for each.
 * The QR size includes its white border and is about 70% of the tag, which leaves room for the
 * hole and the wordmark. It is a starting point until the manufacturer confirms the printable area.
 */
const TAG_SIZES = [
  { tagMm: 27, qrMm: 19 },
  { tagMm: 30, qrMm: 21 },
  { tagMm: 33, qrMm: 23 },
] as const;

/** The four approved tag designs. "qr" is the bare QR with no artwork. */
const DESIGNS = [
  { key: "ivory", label: "Ivory" },
  { key: "glacier", label: "Glacier" },
  { key: "burgundy", label: "Burgundy" },
  { key: "black", label: "Black" },
  { key: "qr", label: "QR only" },
] as const;
type DesignKey = (typeof DESIGNS)[number]["key"];

function ExportLinks({
  id,
  quantity,
  pdfParts,
  sizeMm,
  design,
}: {
  id: string;
  quantity: number;
  pdfParts: number;
  sizeMm: number;
  design: DesignKey;
}) {
  const link = "inline-flex min-h-10 items-center rounded-lg border border-line px-3 text-sm font-semibold hover:bg-subtle";
  const href = (query: string) => `/api/admin/batches/${id}/export?${query}&sizeMm=${sizeMm}${design === "qr" ? "" : `&design=${design}`}`;
  // One ZIP of single files is limited to 20,000 tags on the server; bigger batches use PDF and CSV.
  const zipAllowed = quantity <= 20_000;
  return (
    <div className="flex flex-wrap gap-2">
      <a className={link} href={href("format=csv")} download>
        CSV (serial, code, link)
      </a>
      {Array.from({ length: pdfParts }, (_, index) => (
        <a key={index} className={link} href={href(`format=pdf&part=${index + 1}`)} download>
          {pdfParts === 1 ? "PDF (1 tag per page)" : `PDF part ${index + 1} of ${pdfParts}`}
        </a>
      ))}
      {zipAllowed &&
        (["svg", "eps"] as const).map((format) => (
          <a key={format} className={link} href={href(`format=${format}`)} download>
            {format.toUpperCase()} files (ZIP)
          </a>
        ))}
    </div>
  );
}

function BatchDetails({ id }: { id: string }) {
  const queryClient = useQueryClient();
  const [tagMm, setTagMm] = useState<number>(30);
  const [design, setDesign] = useState<DesignKey>("ivory");
  // With artwork the size is the whole tag; a bare QR file is sized by the derived QR width.
  const sizeMm = design === "qr" ? (TAG_SIZES.find((size) => size.tagMm === tagMm) ?? TAG_SIZES[1]).qrMm : tagMm;
  const detail = useQuery({
    queryKey: ["admin", "batch", id, sizeMm, design],
    queryFn: () => api<BatchDetail>(`/api/admin/batches/${id}?sizeMm=${sizeMm}${design === "qr" ? "" : `&design=${design}`}`),
    placeholderData: (previous) => previous,
  });
  const sell = useMutation({
    mutationFn: () => api<{ changed: number }>(`/api/admin/batches/${id}/mark-sold`, { method: "POST", body: {} }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin"] }),
  });

  if (detail.isPending) return <Loading />;
  if (detail.error) return <Alert>{errorMessage(detail.error)}</Alert>;
  const { print, sampleUrl, pdfParts, batch, byStock } = detail.data;
  const inStock = byStock.IN_STOCK ?? 0;

  return (
    <div className="space-y-4 border-t border-line pt-4">
      {print && (
        <div className="text-sm">
          <p>
            Each QR is <strong>{print.modulesPerSide}×{print.modulesPerSide}</strong> modules (version {print.version}, {print.mode} mode). At{" "}
            {print.qrMm ?? print.physicalMm} mm wide, one module is <strong>{print.moduleMm} mm</strong>.{" "}
            {print.printable ? (
              <span className="text-success">That prints and scans reliably.</span>
            ) : (
              <span className="text-danger">Too small to print reliably. Use a bigger tag.</span>
            )}
          </p>
          {print.inverted && (
            <p className="mt-1 text-muted">
              This design has light dots on a dark tag. Most phone cameras read it, but some scanners do not, so test it on several phones
              before a big print.
            </p>
          )}
          {sampleUrl && <p className="mt-1 break-all font-mono text-xs text-muted">Example: {sampleUrl}</p>}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Design">
        <span className="text-sm font-medium">Design</span>
        {DESIGNS.map((option) => (
          <button
            key={option.key}
            type="button"
            aria-pressed={option.key === design}
            onClick={() => setDesign(option.key)}
            className={`min-h-10 rounded-lg border px-3 text-sm font-semibold ${
              option.key === design ? "border-brand bg-brand text-on-brand" : "border-line hover:bg-subtle"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Tag size">
        <span className="text-sm font-medium">Tag size</span>
        {TAG_SIZES.map((size) => (
          <button
            key={size.tagMm}
            type="button"
            aria-pressed={size.tagMm === tagMm}
            onClick={() => setTagMm(size.tagMm)}
            className={`min-h-10 rounded-lg border px-3 text-sm font-semibold ${
              size.tagMm === tagMm ? "border-brand bg-brand text-on-brand" : "border-line hover:bg-subtle"
            }`}
          >
            {size.tagMm} mm
          </button>
        ))}
      </div>
      <ExportLinks id={id} quantity={batch.quantity} pdfParts={pdfParts} sizeMm={sizeMm} design={design} />
      <p className="text-xs text-muted">
        {design === "qr"
          ? `For a ${tagMm} mm tag the QR is drawn ${sizeMm} mm wide, white border included, and that size is in the file name.`
          : `Each file is the finished ${tagMm} mm ${design} tag with its own QR, and the design and size are in the file name.`}{" "}
        The CSV, the PDF pages and the file names all follow the same order, so the printer can match them.
      </p>

      <div className="rounded-xl bg-subtle p-4 text-sm">
        <p className="font-medium">Stock</p>
        <p className="mt-1 text-muted">
          {Object.entries(byStock)
            .map(([name, count]) => `${count} ${name.toLowerCase().replace("_", " ")}`)
            .join(" · ")}
        </p>
        {inStock > 0 && (
          <div className="mt-3 space-y-2">
            <p className="text-muted">
              Only a tag that is marked sold can be turned on by a customer. Orders will do this when they are packed. For stock you hand to a
              seller yourself, mark the batch as sold here.
            </p>
            {sell.error && <Alert>{errorMessage(sell.error)}</Alert>}
            {sell.data && <Alert tone="success">{sell.data.changed} tags marked as sold.</Alert>}
            <ConfirmButton
              label={`Mark ${inStock.toLocaleString()} in-stock tags as sold`}
              confirmLabel="Yes, mark as sold"
              variant="primary"
              loading={sell.isPending}
              onConfirm={() => sell.mutate()}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default function Batches() {
  const queryClient = useQueryClient();
  const batches = useQuery({ queryKey: KEY, queryFn: async () => (await api<{ batches: Batch[] }>("/api/admin/batches")).batches });
  const [open, setOpen] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [quantity, setQuantity] = useState("1000");
  const [importName, setImportName] = useState("");
  const [csv, setCsv] = useState("");

  const generate = useMutation({
    mutationFn: () => api<{ batch: Batch }>("/api/admin/batches/generate", { method: "POST", body: { name, quantity: Number(quantity) } }),
    onSuccess: async ({ batch }) => {
      setName("");
      await queryClient.invalidateQueries({ queryKey: KEY });
      setOpen(batch.id);
    },
  });

  const importCodes = useMutation({
    mutationFn: () => api<{ batch: Batch }>("/api/admin/batches/import", { method: "POST", body: { name: importName, csv } }),
    onSuccess: async ({ batch }) => {
      setImportName("");
      setCsv("");
      await queryClient.invalidateQueries({ queryKey: KEY });
      setOpen(batch.id);
    },
  });

  const onGenerate = (event: FormEvent) => {
    event.preventDefault();
    generate.mutate();
  };
  const onImport = (event: FormEvent) => {
    event.preventDefault();
    importCodes.mutate();
  };
  const onFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) setCsv(await file.text());
  };

  const importDetails =
    importCodes.error instanceof ApiError && Array.isArray(importCodes.error.details)
      ? (importCodes.error.details as unknown[]).filter((d): d is string => typeof d === "string")
      : [];

  return (
    <div className="space-y-6">
      <PageHeader title="QR batches" subtitle="Every batch is a set of tags with their own QR codes, ready for the printer." />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="font-semibold">Generate new tags</h2>
          <form onSubmit={onGenerate} className="mt-3 space-y-3" noValidate>
            {generate.error && <Alert>{errorMessage(generate.error)}</Alert>}
            <Field label="Batch name" hint="For your own reference, for example “First print run”.">
              <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} required />
            </Field>
            <Field label="How many tags?" hint={`Up to ${MAX_BATCH_SIZE.toLocaleString()}. The first batch is planned as 5,000.`}>
              <Input type="number" inputMode="numeric" min={1} max={MAX_BATCH_SIZE} value={quantity} onChange={(e) => setQuantity(e.target.value)} required />
            </Field>
            <Button type="submit" loading={generate.isPending}>
              Generate
            </Button>
          </form>
        </Card>

        <Card>
          <h2 className="font-semibold">Import existing codes</h2>
          <form onSubmit={onImport} className="mt-3 space-y-3" noValidate>
            {importCodes.error && (
              <Alert>
                {errorMessage(importCodes.error)}
                {importDetails.length > 0 && (
                  <ul className="mt-2 list-disc ps-5">
                    {importDetails.map((d) => (
                      <li key={d}>{d}</li>
                    ))}
                  </ul>
                )}
              </Alert>
            )}
            <Field label="Batch name">
              <Input value={importName} onChange={(e) => setImportName(e.target.value)} maxLength={80} required />
            </Field>
            <Field label="Codes" hint="One code per line, or a CSV with the code in the first column. 6 to 24 letters and digits.">
              <Textarea value={csv} onChange={(e) => setCsv(e.target.value)} placeholder={"K7X9M2QP4A\nB2C3D4E5F6"} required />
            </Field>
            <input type="file" accept=".csv,.txt,text/csv,text/plain" onChange={onFile} className="block text-sm" aria-label="Load codes from a file" />
            <Button type="submit" variant="secondary" loading={importCodes.isPending}>
              Import
            </Button>
          </form>
        </Card>
      </div>

      {batches.isPending && <Loading />}
      {batches.error && <Alert>{errorMessage(batches.error)}</Alert>}
      {batches.data && batches.data.length === 0 && <Empty>No batches yet. Generate your first one above.</Empty>}

      <ul className="space-y-3">
        {batches.data?.map((batch) => (
          <li key={batch.id}>
            <Card>
              <button
                type="button"
                className="flex w-full flex-wrap items-center justify-between gap-2 text-left"
                onClick={() => setOpen(open === batch.id ? null : batch.id)}
                aria-expanded={open === batch.id}
              >
                <span>
                  <span className="block font-semibold">{batch.name}</span>
                  <span className="block text-sm text-muted">
                    {batch.quantity.toLocaleString()} tags · {formatDateTime(batch.createdAt)}
                  </span>
                </span>
                <span className="flex flex-wrap gap-1.5">
                  <Badge tone="brand">{batch.source === "GENERATED" ? "Generated" : "Imported"}</Badge>
                  <Badge tone="success">{batch.byStatus.ACTIVE ?? 0} active</Badge>
                  <Badge tone="neutral">{batch.byStatus.NOT_ACTIVE ?? 0} not active</Badge>
                  {(batch.byStatus.RETIRED ?? 0) > 0 && <Badge tone="danger">{batch.byStatus.RETIRED} retired</Badge>}
                </span>
              </button>
              {open === batch.id && (
                <div className="mt-4">
                  <BatchDetails id={batch.id} />
                </div>
              )}
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
