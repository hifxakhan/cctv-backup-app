import React, { useEffect, useState } from 'react';
import { Card, CardContent, Typography, TextField, CircularProgress, Stack } from '@mui/material';
import { getLogs } from '../../services/api';

function LogViewer() {
  const [logs, setLogs] = useState([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadLogs = async () => {
      const response = await getLogs({ limit: 100 });
      setLogs(response.data.logs || []);
      setLoading(false);
    };
    loadLogs();
  }, []);

  const filtered = logs.filter((line) => line.toLowerCase().includes(filter.toLowerCase()));

  return (
    <Card>
      <CardContent>
        <Typography variant="h5" sx={{ mb: 2 }}>Logs</Typography>
        <TextField label="Filter logs" value={filter} onChange={(event) => setFilter(event.target.value)} sx={{ mb: 2 }} fullWidth />
        {loading ? <CircularProgress /> : (
          <Stack spacing={1} sx={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
            {filtered.map((line, index) => <Typography key={`${line}-${index}`}>{line}</Typography>)}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
}

export default LogViewer;
