import React, { useEffect, useRef, useState } from 'react';
import { useApp } from '../../context/AppContext';
import { casesApi, ApiError } from '../../lib/api';
import type { EvidenceResponse } from '../../lib/apiTypes';
import { X, Upload, FileCheck, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

interface SubmitEvidenceModalProps {
  caseId: number;
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (evidence: EvidenceResponse) => void;
}

/** The backend's real, documented `source_type` vocabulary
 * (`app.detection.device_identifier._SOURCE_TYPE_DEVICE_TYPE`) --
 * never an invented vendor/model taxonomy the backend has no field for. */
const SOURCE_TYPES: Array<{ value: string; label: string }> = [
  { value: 'native_export', label: 'Native DVR/NVR Export' },
  { value: 'raw_dd', label: 'RAW / DD Disk Image' },
  { value: 'e01', label: 'E01 Forensic Image' },
  { value: 'direct_storage', label: 'Direct Storage Device' },
  { value: 'forensic_image', label: 'Forensic Image (other)' },
];

export const SubmitEvidenceModal: React.FC<SubmitEvidenceModalProps> = ({
  caseId,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { currentUser, addToast } = useApp();
  const [evidenceId, setEvidenceId] = useState('');
  const [sourceType, setSourceType] = useState(SOURCE_TYPES[0].value);
  const [description, setDescription] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createdEvidence, setCreatedEvidence] = useState<EvidenceResponse | null>(null);

  useEffect(() => {
    if (isOpen) {
      setEvidenceId(`EV-${Date.now().toString(36).toUpperCase()}`);
      setSourceType(SOURCE_TYPES[0].value);
      setDescription('');
      setFile(null);
      setError(null);
      setCreatedEvidence(null);
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isSubmitting && isOpen) onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isSubmitting, onClose]);

  if (!isOpen) return null;

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files?.[0]) setFile(e.dataTransfer.files[0]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Select an evidence file to upload.');
      return;
    }
    if (!evidenceId.trim()) {
      setError('Evidence ID is required.');
      return;
    }
    setError(null);
    setIsSubmitting(true);

    const form = new FormData();
    form.append('evidence_id', evidenceId.trim());
    form.append('source_type', sourceType);
    if (description.trim()) form.append('source_description', description.trim());
    form.append('file', file);

    try {
      const evidence = await casesApi.uploadEvidence(caseId, form);
      setCreatedEvidence(evidence);
      addToast({
        title: 'Evidence Registered',
        description: `${evidence.evidence_id} uploaded and registered.`,
        type: 'success',
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-sm overflow-y-auto"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) onClose();
      }}
    >
      <div className="w-full max-w-2xl bg-neutral-950 border border-neutral-800 rounded-lg shadow-2xl flex flex-col max-h-[92vh] overflow-hidden my-auto text-neutral-100 font-sans">
        <div className="px-5 py-4 border-b border-neutral-800 bg-neutral-900/90 flex items-center justify-between shrink-0">
          <div>
            <h2 className="text-sm sm:text-base font-mono font-bold uppercase tracking-wider text-neutral-100">
              SUBMIT NEW EVIDENCE
            </h2>
            <p className="text-xs font-mono text-neutral-400 mt-0.5">
              Registered by {currentUser?.display_name ?? 'you'}
            </p>
          </div>
          <button onClick={onClose} disabled={isSubmitting} className="p-1.5 rounded text-neutral-400 hover:text-neutral-100 hover:bg-neutral-800">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {!createdEvidence ? (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="p-3 rounded bg-red-950/50 border border-red-500/40 text-red-300 text-xs font-mono flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <div className="space-y-1.5">
                <label className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-300">
                  Evidence ID
                </label>
                <input
                  type="text"
                  value={evidenceId}
                  onChange={(e) => setEvidenceId(e.target.value)}
                  className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-xs font-mono text-neutral-200 focus:outline-none focus:border-yellow-400"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-300">
                  Source Type
                </label>
                <select
                  value={sourceType}
                  onChange={(e) => setSourceType(e.target.value)}
                  className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-xs font-mono text-neutral-200 focus:outline-none focus:border-yellow-400"
                >
                  {SOURCE_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-300">
                  Notes (optional)
                </label>
                <textarea
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Vendor/camera/location context, seizing officer, etc. Free text -- not independently verified by the backend."
                  className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-xs font-mono text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-yellow-400 resize-none"
                />
              </div>

              <div className="space-y-2">
                <label className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-300">
                  Evidence File
                </label>
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    setIsDragging(true);
                  }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-all ${
                    isDragging ? 'border-yellow-400 bg-yellow-400/10' : file ? 'border-emerald-500/50 bg-emerald-950/10' : 'border-neutral-800 hover:border-neutral-700 bg-neutral-900/40'
                  }`}
                >
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    className="hidden"
                  />
                  <div className="flex flex-col items-center justify-center gap-1.5">
                    {file ? (
                      <>
                        <FileCheck className="w-7 h-7 text-emerald-400" />
                        <div className="text-xs font-mono font-bold text-neutral-200">{file.name}</div>
                        <div className="text-[11px] font-mono text-neutral-400">
                          {(file.size / (1024 * 1024)).toFixed(2)} MB
                        </div>
                      </>
                    ) : (
                      <>
                        <Upload className="w-7 h-7 text-yellow-400/80" />
                        <div className="text-xs font-mono font-bold text-neutral-200">
                          DROP FILE HERE or <span className="text-yellow-400 underline">BROWSE</span>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </form>
          ) : (
            <div className="py-4 space-y-4">
              <div className="p-4 rounded-lg bg-emerald-950/30 border border-emerald-500/40 space-y-3">
                <div className="flex items-center gap-2.5">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  <div>
                    <span className="text-xs font-mono font-bold uppercase text-emerald-400">
                      EVIDENCE REGISTERED
                    </span>
                    <div className="text-lg font-mono font-bold text-neutral-100 mt-0.5">
                      {createdEvidence.evidence_id}
                    </div>
                  </div>
                </div>
                <div className="text-xs font-mono text-neutral-300">
                  Status: {createdEvidence.status} · Source: {createdEvidence.source_type}
                </div>
              </div>
              <p className="text-xs font-mono text-neutral-400 leading-relaxed">
                Run automatic processing from the case overview to hash, identify, enumerate
                recordings, and analyze this evidence.
              </p>
            </div>
          )}
        </div>

        <div className="px-5 py-3.5 border-t border-neutral-800 bg-neutral-900/90 flex items-center justify-between shrink-0">
          {!createdEvidence ? (
            <>
              <button onClick={onClose} disabled={isSubmitting} className="px-4 py-2 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-300 text-xs font-mono transition-colors disabled:opacity-50">
                CANCEL
              </button>
              <button
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="px-6 py-2 rounded bg-yellow-400 hover:bg-yellow-300 text-neutral-950 font-bold text-xs font-mono uppercase tracking-wider flex items-center gap-2 transition-all disabled:opacity-50"
              >
                {isSubmitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                <span>{isSubmitting ? 'UPLOADING…' : 'SUBMIT EVIDENCE'}</span>
              </button>
            </>
          ) : (
            <button
              onClick={() => {
                onSuccess?.(createdEvidence);
                onClose();
              }}
              className="w-full py-2.5 rounded bg-yellow-400 hover:bg-yellow-300 text-neutral-950 font-bold text-xs font-mono uppercase tracking-wider flex items-center justify-center gap-2 transition-all"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>VIEW IN EVIDENCE WORKSPACE</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
