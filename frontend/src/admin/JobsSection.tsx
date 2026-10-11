import { useEffect, useState } from 'react';
import type { APIError } from '../common/types';
import { adminAPI } from './api';
import type { JobRunResult, JobStatus } from './types';
import { formatFutureTime, formatRelativeTime } from './utils';

const errorDetail = (err: unknown, fallback: string): string => {
  const detail = (err as APIError).detail;
  return typeof detail === 'string' ? detail : fallback;
};

// Every sub-site's scheduled jobs, when they last ran and next run, with a
// button to run each one now.
export default function JobsSection() {
  const [jobs, setJobs] = useState<JobStatus[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [running, setRunning] = useState<Record<string, boolean>>({});
  const [results, setResults] = useState<Record<string, JobRunResult | null>>({});

  const refresh = () => {
    adminAPI
      .getJobStatuses()
      .then(setJobs)
      .catch((err) => setLoadError(errorDetail(err, 'Failed to load scheduled jobs')));
  };

  useEffect(refresh, []);

  const handleRun = async (jobId: string) => {
    setRunning((prev) => ({ ...prev, [jobId]: true }));
    setResults((prev) => ({ ...prev, [jobId]: null }));
    try {
      const result = await adminAPI.triggerJob(jobId);
      setResults((prev) => ({ ...prev, [jobId]: result }));
      refresh();
    } catch (err) {
      setResults((prev) => ({
        ...prev,
        [jobId]: { success: false, message: errorDetail(err, 'Job failed') },
      }));
    } finally {
      setRunning((prev) => ({ ...prev, [jobId]: false }));
    }
  };

  return (
    <section className="admin-section">
      <h2>Scheduled Jobs</h2>
      {loadError ? (
        <div className="error-message">{loadError}</div>
      ) : jobs === null ? (
        <p>Loading job statuses…</p>
      ) : (
        <div className="scrollable-table-wrapper">
          <table className="audit-log-table">
            <thead>
              <tr>
                <th>Job</th>
                <th>Last Run</th>
                <th>Next Run</th>
                <th>Action</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td>
                    {job.name}
                    <div className="staff-admin-job-area">{job.area}</div>
                  </td>
                  <td className="audit-log-time">{formatRelativeTime(job.last_run_at)}</td>
                  <td className="audit-log-time">{formatFutureTime(job.next_run_at)}</td>
                  <td>
                    {job.can_run ? (
                      <button
                        className="btn-primary btn-small"
                        onClick={() => handleRun(job.id)}
                        disabled={!!running[job.id]}
                      >
                        {running[job.id] ? 'Running…' : 'Run Now'}
                      </button>
                    ) : (
                      <span className="field-hint">Scheduled only</span>
                    )}
                  </td>
                  <td>
                    {results[job.id] && (
                      <span className={results[job.id]!.success ? 'text-success' : 'error-message'}>
                        {results[job.id]!.message}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
