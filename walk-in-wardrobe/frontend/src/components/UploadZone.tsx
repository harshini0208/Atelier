import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Inspo } from "../types";
import { ErrorBox, Icon } from "./ui";

const STEPS = ["Finding the pieces in your outfit…", "Reading colours, fabrics and fit…", "Drawing boxes around each piece…",
  "Almost there…"];

export function Analyzing({ src }: { src: string | null }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => setI((x) => Math.min(x + 1, STEPS.length - 1)), 2600);
    return () => window.clearInterval(t);
  }, []);
  return (
    <div className="stack" style={{ alignItems: "center" }} role="status" aria-live="polite">
      <div className="inspo-frame" style={{ maxWidth: 260 }}>
        {src ? <img src={src} alt="Your uploaded inspiration" /> : <div className="skeleton" style={{ aspectRatio: "9/16" }} />}
        <div className="scan" />
      </div>
      <div className="row"><span className="spinner" /> <b>{STEPS[i]}</b></div>
      <span className="small muted">We only look at clothing, never at who's wearing it.</span>
    </div>
  );
}

/** Upload a screenshot. With a folderId it lands in that folder; without one (landing page) pieces are filed later. */
export default function UploadZone({ folderId, compact = false }: { folderId?: number; compact?: boolean }) {
  const qc = useQueryClient();
  const nav = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return api.post<Inspo>(folderId ? `/folders/${folderId}/inspo` : "/inspo", fd);
    },
    onSuccess: (inspo) => {
      qc.invalidateQueries({ queryKey: folderId ? ["folder", folderId] : ["unfiled"] });
      qc.invalidateQueries({ queryKey: ["folders"] });
      nav(`/inspo/${inspo.id}`);
    },
    onSettled: () => setPreview(null),
  });

  const take = (file: File | undefined | null) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      upload.reset();
      alert("Please choose an image (PNG, JPG or WebP screenshot).");
      return;
    }
    setPreview(URL.createObjectURL(file));
    upload.mutate(file);
  };

  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const f = Array.from(e.clipboardData?.files ?? []).find((x) => x.type.startsWith("image/"));
      if (f) take(f);
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [folderId]);

  if (upload.isPending) return <div className="card pad"><Analyzing src={preview} /></div>;

  return (
    <div
      className={`dropzone ${drag ? "drag" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); take(e.dataTransfer.files?.[0]); }}
    >
      <input ref={input} type="file" accept="image/*" hidden onChange={(e) => take(e.target.files?.[0])} aria-label="Choose an inspo screenshot" />
      <div className="stack" style={{ alignItems: "center", gap: compact ? 6 : 10 }}>
        {!compact && <Icon name="upload" size={28} />}
        <button className="btn btn-primary" onClick={() => input.current?.click()}><Icon name="upload" /> Upload inspo</button>
        <span className="small muted">Drop a screenshot here, pick a file, or paste (Ctrl/⌘ V). Instagram, Pinterest, anything.</span>
      </div>
      {upload.error && <div style={{ marginTop: 12 }}><ErrorBox error={upload.error} /></div>}
    </div>
  );
}
