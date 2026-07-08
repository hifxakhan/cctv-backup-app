import React, { useEffect, useState } from 'react';
import { Card, CardContent, Grid, Typography, Button, Stack, Chip, CircularProgress, Alert } from '@mui/material';
import { getConfig, getStats, getUploads, startSync, startOnvifSync, getOnvifSdInfo, getOnvifRecordings } from '../../services/api';
import { useWebSocket } from '../../hooks/useWebSocket';

function Dashboard() {
  const [stats, setStats] = useState({ total_files: 0, total_size_gb: 0, last_upload: null });
  const [uploads, setUploads] = useState([]);
  const [onvifStatus, setOnvifStatus] = useState(null);
  const [recordings, setRecordings] = useState([]);
  const [protocol, setProtocol] = useState('onvif');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { events } = useWebSocket();

  useEffect(() => {
    const loadData = async () => {
      try {
        const [statsResponse, uploadsResponse, onvifInfoResponse, recordingsResponse, configResponse] = await Promise.all([
          getStats(),
          getUploads({ limit: 5 }),
          getOnvifSdInfo().catch(() => ({ data: { status: 'unavailable' } })),
          getOnvifRecordings({ days_back: 3 }).catch(() => ({ data: { recordings: [] } })),
          getConfig().catch(() => ({ data: { protocol_type: 'onvif' } })),
        ]);
        setStats(statsResponse.data);
        setUploads(uploadsResponse.data);
        setOnvifStatus(onvifInfoResponse.data);
        setRecordings(recordingsResponse.data.recordings || []);
        setProtocol(configResponse.data.protocol_type || 'onvif');
        setError('');
      } catch (err) {
        setError('Backend is not reachable. Start the Flask server on port 5000 to enable live data.');
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const handleSync = async () => {
    try {
      await startSync();
      setLoading(true);
      const statsResponse = await getStats();
      setStats(statsResponse.data);
      setError('');
    } catch (err) {
      setError('Unable to start sync because the backend is not reachable.');
    } finally {
      setLoading(false);
    }
  };

  const handleOnvifSync = async () => {
    try {
      await startOnvifSync();
      setError('');
    } catch (err) {
      setError('Unable to start ONVIF sync.');
    }
  };

  return (
    <div>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <div>
          <Typography variant="h4">Overview</Typography>
          <Typography color="text.secondary">Monitor backup health and recent activity.</Typography>
        </div>
        <Stack direction="row" spacing={2}>
          <Button variant="contained" onClick={handleSync}>Start Sync</Button>
          {protocol === 'onvif' ? (<Button variant="outlined" onClick={handleOnvifSync}>Sync ONVIF</Button>) : null}
        </Stack>
      </Stack>

      {error ? <Alert severity="warning" sx={{ mb: 3 }}>{error}</Alert> : null}

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={4}>
          <Card><CardContent><Typography color="text.secondary">Total Uploads</Typography><Typography variant="h4">{stats.total_files}</Typography></CardContent></Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card><CardContent><Typography color="text.secondary">Total Data</Typography><Typography variant="h4">{stats.total_size_gb.toFixed(2)} GB</Typography></CardContent></Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card><CardContent><Typography color="text.secondary">Last Upload</Typography><Typography variant="h6">{stats.last_upload || 'No uploads yet'}</Typography></CardContent></Card>
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Card><CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>Recent Uploads</Typography>
            {loading ? <CircularProgress /> : uploads.map((item) => <Typography key={item.id} sx={{ mb: 1 }}>{item.file_name} • {item.file_size} bytes</Typography>)}
          </CardContent></Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card><CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>Live Status</Typography>
            {events.slice(-5).reverse().map((event, index) => <Chip key={`${event.message}-${index}`} label={event.message} sx={{ mb: 1, display: 'block' }} />)}
          </CardContent></Card>
        </Grid>
      </Grid>

      <Grid container spacing={3} sx={{ mt: 1 }}>
        <Grid item xs={12} md={6}>
          <Card><CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>Active Protocol</Typography>
            <Typography color="text.secondary" sx={{ textTransform: 'uppercase' }}>{protocol}</Typography>
            <Typography variant="body2">Status: {protocol === 'onvif' ? (onvifStatus?.status || 'not configured') : 'FTP configured'}</Typography>
            <Typography variant="body2">Host: {protocol === 'onvif' ? (onvifStatus?.host || 'not configured') : 'configured in settings'}</Typography>
          </CardContent></Card>
        </Grid>
        {protocol === 'onvif' ? (
          <Grid item xs={12} md={6}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>ONVIF Status</Typography>
              <Typography color="text.secondary">{onvifStatus?.status || 'unknown'}</Typography>
              <Typography variant="body2">Host: {onvifStatus?.host || 'not configured'}</Typography>
              <Typography variant="body2">Port: {onvifStatus?.port || 'not configured'}</Typography>
            </CardContent></Card>
          </Grid>
        ) : null}
      </Grid>

      {protocol === 'onvif' ? (
        <Grid container spacing={3} sx={{ mt: 1 }}>
          <Grid item xs={12}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>Recent Recordings</Typography>
              {recordings.length === 0 ? <Typography color="text.secondary">No recordings found.</Typography> : recordings.slice(0, 5).map((item) => <Typography key={item.token || item.name} sx={{ mb: 1 }}>{item.name}</Typography>)}
            </CardContent></Card>
          </Grid>
        </Grid>
      ) : null}
    </div>
  );
}

export default Dashboard;
