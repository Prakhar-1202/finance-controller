import React, { useState } from "react";
import { UploadCloud, Loader2, CheckCircle2, AlertCircle, FileText } from "lucide-react";

import { uploadDataset } from "../../services/api";

// Fixed slots the backend expects — labels are for display only, the
// original filenames are never sent anywhere except inside these files.
const FILE_SLOTS = [
  { key: "bankStatement", label: "Bank Statement" },
  { key: "razorpaySettlement", label: "Razorpay Settlement" },
  { key: "internalLedger", label: "Internal Ledger" },
];

function isCsv(file) {
  return !!file && /\.csv$/i.test(file.name);
}

/**
 * Lets the user upload the three reconciliation CSVs and swap them in as
 * the active dataset. On a successful upload, calls `onUploaded(response)`
 * with the backend's response (which includes the new `data_dir`) — the
 * caller (Dashboard.jsx, via App.jsx's onDatasetUploaded) is responsible
 * for updating dataDir/datasetVersion state.
 */
function UploadDataset({ onUploaded = () => {} }) {
  const [files, setFiles] = useState({
    bankStatement: null,
    razorpaySettlement: null,
    internalLedger: null,
  });
  const [isUploading, setIsUploading] = useState(false);
  const [feedback, setFeedback] = useState(null); // { type: "error"|"success", message }

  const allSelected = FILE_SLOTS.every((slot) => !!files[slot.key]);

  const handleFileChange = (key) => (event) => {
    const file = event.target.files?.[0] || null;
    setFeedback(null);

    if (file && !isCsv(file)) {
      setFeedback({ type: "error", message: `${file.name} is not a .csv file.` });
      event.target.value = "";
      return;
    }

    setFiles((prev) => ({ ...prev, [key]: file }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!allSelected || isUploading) return;

    setIsUploading(true);
    setFeedback(null);

    try {
      const response = await uploadDataset(files);

      setFeedback({
        type: "success",
        message: "Dataset uploaded successfully. Refreshing reconciliation data...",
      });
      setFiles({ bankStatement: null, razorpaySettlement: null, internalLedger: null });

      onUploaded(response);

      setTimeout(() => {
        setFeedback((prev) => (prev?.type === "success" ? null : prev));
      }, 5000);
    } catch (err) {
      setFeedback({
        type: "error",
        message: err.message || "Upload failed. Please check the files and try again.",
      });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="upload-dataset" style={{ marginBottom: "20px" }}>
      {feedback?.type === "error" && (
        <div className="alert-banner alert-banner-error" role="alert" style={{ marginBottom: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <AlertCircle size={16} />
            <span>{feedback.message}</span>
          </div>
        </div>
      )}

      {feedback?.type === "success" && (
        <div className="alert-banner alert-banner-success" role="status" style={{ marginBottom: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <CheckCircle2 size={16} />
            <span>{feedback.message}</span>
          </div>
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "12px",
        }}
      >
        {FILE_SLOTS.map((slot) => (
          <label
            key={slot.key}
            className="btn-secondary"
            style={{
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
            }}
            title={`Upload ${slot.label} CSV`}
          >
            <FileText size={14} />
            <span>{files[slot.key]?.name || slot.label}</span>
            <input
              type="file"
              accept=".csv"
              onChange={handleFileChange(slot.key)}
              style={{ display: "none" }}
            />
          </label>
        ))}

        <button
          type="submit"
          className="btn-primary"
          disabled={!allSelected || isUploading}
          aria-busy={isUploading}
          title="Upload dataset and make it active"
        >
          {isUploading ? <Loader2 size={14} className="spinning" /> : <UploadCloud size={14} />}
          <span>{isUploading ? "Uploading..." : "Upload Dataset"}</span>
        </button>
      </form>
    </div>
  );
}

export default UploadDataset;
