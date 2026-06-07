import React, { useState, useEffect } from 'react';
import styles from './ScanHistory.module.css';

const ScanHistory = ({ token, backendUrl }) => {
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchScans = async () => {
      try {
        const res = await fetch(`${backendUrl}/api/results`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        if (res.ok) {
          const data = await res.json();
          setScans(data);
        }
      } catch (err) {
        console.error("Failed to fetch scan history", err);
      } finally {
        setLoading(false);
      }
    };

    fetchScans();
  }, [token, backendUrl]);

  if (loading) {
    return <div className={styles.loading}>Loading scan history...</div>;
  }

  return (
    <div className={styles.historyContainer}>
      <h2>Scan History</h2>
      {scans.length === 0 ? (
        <p>No scans found.</p>
      ) : (
        <table className={styles.scanTable}>
          <thead>
            <tr>
              <th>ID</th>
              <th>Repository</th>
              <th>Status</th>
              <th>Stage</th>
              <th>Date</th>
              <th>PR URL</th>
            </tr>
          </thead>
          <tbody>
            {scans.map(scan => (
              <tr key={scan.scan_id}>
                <td>{scan.scan_id.slice(0, 8)}</td>
                <td>{scan.repo_url}</td>
                <td>
                  <span className={`${styles.statusBadge} ${styles[scan.status]}`}>
                    {scan.status}
                  </span>
                </td>
                <td>{scan.stage}</td>
                <td>{new Date(scan.created_at).toLocaleString()}</td>
                <td>
                  {scan.pr_url ? (
                    <a href={scan.pr_url} target="_blank" rel="noopener noreferrer">View PR</a>
                  ) : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default ScanHistory;
