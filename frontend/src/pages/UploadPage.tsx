import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { Download, FileText, Upload } from 'lucide-react';
import { useUpload } from '../hooks/usePortfolio';
import { analyzePortfolio } from '../api/client';

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [previousFile, setPreviousFile] = useState<File | null>(null);
  const navigate = useNavigate();
  const upload = useUpload();

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted.length) setFile(accepted[0]);
  }, []);
  const onDropPrevious = useCallback((accepted: File[]) => {
    if (accepted.length) setPreviousFile(accepted[0]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'], 'text/plain': ['.csv'] },
    maxFiles: 1,
    multiple: false,
  });
  const {
    getRootProps: getPrevRootProps,
    getInputProps: getPrevInputProps,
    isDragActive: isPrevDragActive,
  } = useDropzone({
    onDrop: onDropPrevious,
    accept: { 'text/csv': ['.csv'], 'text/plain': ['.csv'] },
    maxFiles: 1,
    multiple: false,
  });

  const handleSubmit = async () => {
    if (!file) return;
    const current = await upload.mutateAsync({ file });
    if (previousFile) {
      const previous = await upload.mutateAsync({
        file: previousFile,
      });
      // Kick off analytics for both portfolios so the Progress tab has data.
      await Promise.all([
        analyzePortfolio(previous.portfolio_id),
        analyzePortfolio(current.portfolio_id),
      ]);
      navigate(`/portfolio/${current.portfolio_id}?previous=${previous.portfolio_id}`);
      return;
    }
    await analyzePortfolio(current.portfolio_id);
    navigate(`/portfolio/${current.portfolio_id}`);
  };

  const errorMessage =
    upload.isError &&
    (((upload.error as any)?.response?.data?.detail as string) ||
      (upload.error as Error)?.message ||
      'Upload failed.');

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold mb-2">Upload Your Trade History</h1>
      <p className="text-gray-500 mb-8">
        Upload a CSV export from any brokerage and we handle the rest.
      </p>

      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-primary-500 bg-primary-50'
            : 'border-gray-300 hover:border-primary-400 bg-white'
        }`}
      >
        <input {...getInputProps()} />
        {file ? (
          <div className="flex items-center justify-center gap-3">
            <FileText className="text-primary-600" />
            <span className="font-medium">{file.name}</span>
            <span className="text-gray-400 text-sm">
              ({(file.size / 1024).toFixed(1)} KB)
            </span>
          </div>
        ) : (
          <div>
            <Upload className="mx-auto mb-3 text-gray-400" size={40} />
            <p className="font-medium">Drop your CSV here or click to browse</p>
            <p className="text-sm text-gray-400 mt-1">
              Works with any broker. We detect ticker, action, quantity,
              price and date columns automatically.
            </p>
          </div>
        )}
      </div>

      <div className="mt-4">
        <p className="text-sm font-medium mb-2">Previous CSV (optional for Progress tab)</p>
        <div
          {...getPrevRootProps()}
          className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
            isPrevDragActive
              ? 'border-primary-500 bg-primary-50'
              : 'border-gray-300 hover:border-primary-400 bg-white'
          }`}
        >
          <input {...getPrevInputProps()} />
          {previousFile ? (
            <div className="flex items-center justify-center gap-3">
              <FileText className="text-primary-600" />
              <span className="font-medium">{previousFile.name}</span>
              <span className="text-gray-400 text-sm">
                ({(previousFile.size / 1024).toFixed(1)} KB)
              </span>
            </div>
          ) : (
            <p className="text-sm text-gray-500">
              Upload an earlier CSV export to unlock Progress comparison.
            </p>
          )}
        </div>
      </div>

      <button
        onClick={handleSubmit}
        disabled={!file || upload.isPending}
        className="mt-6 w-full bg-primary-600 text-white py-3 rounded-lg font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {upload.isPending ? 'Uploading…' : 'Analyze Portfolio'}
      </button>

      {upload.isSuccess && upload.data?.detected_format && (
        <p className="mt-3 text-sm text-gray-500">
          Detected format: {upload.data.detected_format}.
        </p>
      )}

      {errorMessage && (
        <p className="mt-3 text-danger text-sm">{errorMessage}</p>
      )}

      <div className="mt-8 p-4 bg-white border border-gray-200 rounded-lg text-sm flex items-start gap-3">
        <Download size={18} className="text-primary-600 mt-0.5 shrink-0" />
        <div>
          <p className="font-medium">Need test CSV files?</p>
          <p className="text-gray-500">
            <a href="/sample_trades.csv" download className="text-primary-600 underline">
              Single sample CSV
            </a>
            {' '}or{' '}
            <a href="/sample_trades_previous.csv" download className="text-primary-600 underline">
              Previous-period sample
            </a>
            {' '}+{' '}
            <a href="/sample_trades_current.csv" download className="text-primary-600 underline">
              Current-period sample
            </a>
            {' '}for Progress comparison.
          </p>
        </div>
      </div>
    </div>
  );
}
