import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  Alert,
  Button,
  Card,
  CardContent,
  FormControl,
  FormHelperText,
  Grid,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
  Radio,
  RadioGroup,
  FormControlLabel,
  FormLabel,
  Divider,
  Box,
  Chip,
  CircularProgress,
} from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import CloudIcon from '@mui/icons-material/Cloud';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import LogoutIcon from '@mui/icons-material/Logout';
import RefreshIcon from '@mui/icons-material/Refresh';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import './Settings.css';
import {
  browseFolder,
  getConfig,
  getProtocol,
  saveConfig,
  saveProtocol,
  checkDriveStatus,
  disconnectDrive,
  connectDrive,
  saveUserToken,
} from '../../services/api';

const initialForm = {
  protocol_type: 'onvif',
  storage_destination: 'both',
  ftp_host: '',
  ftp_port: '21',
  ftp_user: '',
  ftp_password: '',
  ftp_path: '/',
  drive_folder: 'CCTV_Backup',
  sync_interval: '60',
  onvif_enabled: 'true',
  onvif_host: '',
  onvif_port: '80',
  onvif_user: '',
  onvif_password: '',
  onvif_days_back: '3',
  local_storage_path: 'D:\\CCTV_Recordings',
};

function Settings() {
  const [form, setForm] = useState(initialForm);
  const [status, setStatus] = useState({ type: 'success', message: '' });
  const [errors, setErrors] = useState({});
  const folderInputRef = useRef(null);
  const [driveAuth, setDriveAuth] = useState({
    loading: true,
    authenticated: false,
    authMode: null,
    email: null,
  });

  // Check Google Drive auth status on mount
  const checkDriveAuth = useCallback(async () => {
    console.log('🔄 Checking drive status...');
    setDriveAuth((prev) => ({ ...prev, loading: true }));
    try {
      const data = await checkDriveStatus();
      console.log('📡 Drive status response:', data);
      // ✅ Force the state update even if data is empty
      setDriveAuth({
        loading: false,
        authenticated: data.authenticated === true,
        authMode: data.auth_mode || null,
        email: data.user?.email || null,
      });
      if (data.authenticated) {
        setStatus({ type: 'success', message: `Connected as ${data.user?.email}` });
      }
    } catch (error) {
      console.error('❌ Status check failed:', error);
      setDriveAuth({ loading: false, authenticated: false, authMode: null, email: null });
    }
  }, []);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const [protocolResponse, configResponse] = await Promise.all([getProtocol(), getConfig()]);
        setForm((current) => ({
          ...current,
          ...configResponse.data,
          protocol_type: protocolResponse.data.protocol_type || configResponse.data.protocol_type || 'onvif',
        }));
        setStatus({ type: 'success', message: 'Settings loaded.' });
      } catch (error) {
        setStatus({ type: 'error', message: 'Unable to load settings.' });
      }
    };

    loadConfig();
    checkDriveAuth();
  }, [checkDriveAuth]);

  // Listen for OAuth success message from popup
  useEffect(() => {
    const handleMessage = (event) => {
      console.log('📨 Received message:', event.data);
      if (event.data?.type === 'drive_connected' && event.data?.token) {
        console.log('✅ Drive connected message received! Token:', event.data.token);
        saveUserToken(event.data.token);
        checkDriveAuth();
      }
    };
    window.addEventListener('message', handleMessage);
    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, [checkDriveAuth]);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
    if (errors[name]) {
      setErrors((current) => ({ ...current, [name]: '' }));
    }
  };

  const handleProtocolChange = async (event) => {
    const nextProtocol = event.target.value;
    setForm((current) => ({ ...current, protocol_type: nextProtocol }));
    try {
      await saveProtocol(nextProtocol);
      setStatus({ type: 'success', message: `Protocol switched to ${nextProtocol.toUpperCase()}.` });
    } catch (error) {
      setStatus({ type: 'error', message: 'Unable to switch protocol.' });
    }
  };

  const validateForm = (values) => {
    const validationErrors = {};
    const protocol = values.protocol_type || 'onvif';

    if (protocol === 'onvif') {
      if (!values.onvif_host) validationErrors.onvif_host = 'ONVIF host is required';
      if (!values.onvif_user) validationErrors.onvif_user = 'ONVIF username is required';
      if (!values.onvif_password) validationErrors.onvif_password = 'ONVIF password is required';
      if (values.storage_destination !== 'google_drive' && !values.local_storage_path) {
        validationErrors.local_storage_path = 'Local storage path is required';
      }
      if (values.storage_destination !== 'local' && !values.drive_folder) {
        validationErrors.drive_folder = 'Google Drive folder is required';
      }
    } else {
      if (!values.ftp_host) validationErrors.ftp_host = 'FTP host is required';
      if (!values.ftp_user) validationErrors.ftp_user = 'FTP username is required';
      if (!values.ftp_password) validationErrors.ftp_password = 'FTP password is required';
      if (!values.ftp_path) validationErrors.ftp_path = 'FTP path is required';
      if (values.storage_destination !== 'google_drive' && !values.local_storage_path) {
        validationErrors.local_storage_path = 'Local storage path is required';
      }
      if (values.storage_destination !== 'local' && !values.drive_folder) {
        validationErrors.drive_folder = 'Google Drive folder is required';
      }
    }

    return validationErrors;
  };

  const handleBrowseFolder = async () => {
    try {
      const response = await browseFolder();
      if (response.data.status === 'success' && response.data.path) {
        setForm((current) => ({ ...current, local_storage_path: response.data.path }));
        if (errors.local_storage_path) {
          setErrors((current) => ({ ...current, local_storage_path: '' }));
        }
        setStatus({ type: 'success', message: `Folder selected: ${response.data.path}` });
      }
    } catch (_backendError) {
      if (folderInputRef.current) {
        folderInputRef.current.value = '';
        folderInputRef.current.click();
      }
    }
  };

  const handleFolderSelected = (event) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      const relativePath = files[0].webkitRelativePath;
      const separator = relativePath.includes('\\') ? '\\' : '/';
      const folderName = relativePath.split(separator)[0];
      setForm((current) => ({ ...current, local_storage_path: folderName }));
      if (errors.local_storage_path) {
        setErrors((current) => ({ ...current, local_storage_path: '' }));
      }
      setStatus({ type: 'success', message: `Folder selected: ${folderName}` });
    }
  };

  const handleConnectDrive = () => {
    const width = 500;
    const height = 600;
    const left = window.screen.width / 2 - width / 2;
    const top = window.screen.height / 2 - height / 2;

    window.open(
      'https://cctv-backup.onrender.com/api/drive/auth?include_granted_scopes=false&prompt=consent',
      'Connect Google Drive',
      `width=${width},height=${height},left=${left},top=${top}`
    );

    setStatus({
      type: 'info',
      message: 'A Google login window has opened. After signing in, this page will automatically detect the connection.',
    });
  };

  const handleDisconnectDrive = async () => {
    try {
      await disconnectDrive();
      setDriveAuth({ loading: false, authenticated: false, authMode: null, email: null });
      setStatus({ type: 'success', message: 'Google Drive disconnected.' });
    } catch (error) {
      setStatus({ type: 'error', message: 'Unable to disconnect Google Drive.' });
    }
  };

  const handleSave = async () => {
    const validationErrors = validateForm(form);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      setStatus({ type: 'error', message: 'Please complete the required fields for the selected protocol.' });
      return;
    }

    try {
      const response = await saveConfig({ ...form, protocol_type: form.protocol_type || 'onvif' });
      setStatus({ type: 'success', message: response.data.message || 'Settings saved successfully.' });
      setErrors({});
    } catch (error) {
      setStatus({ type: 'error', message: error.response?.data?.message || 'Unable to save settings.' });
    }
  };

  return (
    <Card className="settings-card">
      <CardContent>
        <Typography variant="h5" sx={{ mb: 2 }}>Configuration</Typography>
        {status.message ? (
          <Alert
            severity={status.type === 'error' ? 'error' : status.type === 'info' ? 'info' : 'success'}
            sx={{ mb: 2 }}
          >
            {status.message}
          </Alert>
        ) : null}

        <Grid container spacing={2}>
          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel id="protocol-select-label">Protocol Type</InputLabel>
              <Select
                labelId="protocol-select-label"
                label="Protocol Type"
                name="protocol_type"
                value={form.protocol_type}
                onChange={handleProtocolChange}
              >
                <MenuItem value="onvif">ONVIF</MenuItem>
                <MenuItem value="ftp">FTP</MenuItem>
              </Select>
              <FormHelperText>Choose the transport used to access your camera recordings.</FormHelperText>
            </FormControl>
          </Grid>

          {/* Storage Destination */}
          <Grid item xs={12}>
            <Divider sx={{ my: 1 }} />
            <FormControl component="fieldset">
              <FormLabel component="legend">Storage Destination</FormLabel>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                Choose where to save recordings after downloading from the camera.
              </Typography>
              <RadioGroup
                row
                name="storage_destination"
                value={form.storage_destination}
                onChange={handleChange}
              >
                <FormControlLabel value="local" control={<Radio />} label="Local Storage" />
                <FormControlLabel value="google_drive" control={<Radio />} label="Google Drive" />
                <FormControlLabel value="both" control={<Radio />} label="Both" />
              </RadioGroup>
            </FormControl>
          </Grid>

          {form.protocol_type === 'onvif' ? (
            <>
              <Grid item xs={12} md={6}>
                <TextField fullWidth label="ONVIF Host" name="onvif_host" value={form.onvif_host} onChange={handleChange} error={Boolean(errors.onvif_host)} helperText={errors.onvif_host} />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField fullWidth label="ONVIF Port" name="onvif_port" value={form.onvif_port} onChange={handleChange} />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField fullWidth label="ONVIF User" name="onvif_user" value={form.onvif_user} onChange={handleChange} error={Boolean(errors.onvif_user)} helperText={errors.onvif_user} />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField fullWidth label="ONVIF Password" name="onvif_password" type="password" value={form.onvif_password} onChange={handleChange} error={Boolean(errors.onvif_password)} helperText={errors.onvif_password} />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField fullWidth label="ONVIF Days Back" name="onvif_days_back" value={form.onvif_days_back} onChange={handleChange} />
              </Grid>

              {(form.storage_destination === 'local' || form.storage_destination === 'both') && (
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    label="Local Storage Path"
                    name="local_storage_path"
                    value={form.local_storage_path}
                    onChange={handleChange}
                    error={Boolean(errors.local_storage_path)}
                    helperText={errors.local_storage_path}
                    InputProps={{
                      endAdornment: (
                        <Tooltip title="Browse for folder">
                          <IconButton onClick={handleBrowseFolder} edge="end">
                            <FolderOpenIcon />
                          </IconButton>
                        </Tooltip>
                      ),
                    }}
                  />
                </Grid>
              )}
            </>
          ) : (
            <>
              <Grid item xs={12} md={6}>
                <TextField fullWidth label="FTP Host" name="ftp_host" value={form.ftp_host} onChange={handleChange} error={Boolean(errors.ftp_host)} helperText={errors.ftp_host} />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField fullWidth label="FTP Port" name="ftp_port" value={form.ftp_port} onChange={handleChange} />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField fullWidth label="FTP User" name="ftp_user" value={form.ftp_user} onChange={handleChange} error={Boolean(errors.ftp_user)} helperText={errors.ftp_user} />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField fullWidth label="FTP Password" name="ftp_password" type="password" value={form.ftp_password} onChange={handleChange} error={Boolean(errors.ftp_password)} helperText={errors.ftp_password} />
              </Grid>
              <Grid item xs={12}>
                <TextField fullWidth label="FTP Path" name="ftp_path" value={form.ftp_path} onChange={handleChange} error={Boolean(errors.ftp_path)} helperText={errors.ftp_path} />
              </Grid>

              {(form.storage_destination === 'local' || form.storage_destination === 'both') && (
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    label="Local Storage Path"
                    name="local_storage_path"
                    value={form.local_storage_path}
                    onChange={handleChange}
                    error={Boolean(errors.local_storage_path)}
                    helperText={errors.local_storage_path}
                    InputProps={{
                      endAdornment: (
                        <Tooltip title="Browse for folder">
                          <IconButton onClick={handleBrowseFolder} edge="end">
                            <FolderOpenIcon />
                          </IconButton>
                        </Tooltip>
                      ),
                    }}
                  />
                </Grid>
              )}
            </>
          )}

          {/* Google Drive Section */}
          {(form.storage_destination === 'google_drive' || form.storage_destination === 'both') && (
            <>
              <Grid item xs={12}>
                <Divider sx={{ my: 1 }} />
                <Typography variant="subtitle1" sx={{ mb: 1 }}>
                  <CloudIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                  Google Drive
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Google Drive Folder"
                  name="drive_folder"
                  value={form.drive_folder}
                  onChange={handleChange}
                  error={Boolean(errors.drive_folder)}
                  helperText={errors.drive_folder || 'Folder name in Google Drive where files will be saved'}
                />
              </Grid>

              <Grid item xs={12} md={6}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, height: '100%', pt: 1, flexWrap: 'wrap' }}>
                  {driveAuth.loading ? (
                    <CircularProgress size={24} />
                  ) : driveAuth.authenticated ? (
                    <>
                      <Chip
                        icon={<CheckCircleIcon />}
                        label={`Connected${driveAuth.email ? ` (${driveAuth.email})` : ''}`}
                        color="success"
                        variant="outlined"
                      />
                      <Button
                        variant="outlined"
                        color="error"
                        size="small"
                        startIcon={<LogoutIcon />}
                        onClick={handleDisconnectDrive}
                      >
                        Disconnect
                      </Button>
                    </>
                  ) : (
                    <>
                      <Chip
                        icon={<CloudOffIcon />}
                        label="Not Connected"
                        color="default"
                        variant="outlined"
                      />
                      <Button
                        variant="contained"
                        size="small"
                        startIcon={<CloudIcon />}
                        onClick={handleConnectDrive}
                      >
                        Connect Google Drive
                      </Button>
                      <Button
                        variant="outlined"
                        size="small"
                        startIcon={<RefreshIcon />}
                        onClick={checkDriveAuth}
                      >
                        Refresh
                      </Button>
                    </>
                  )}
                </Box>
              </Grid>
              {!driveAuth.authenticated && !driveAuth.loading && (
                <Grid item xs={12}>
                  <Alert severity="info" sx={{ mt: 1 }}>
                    <strong>Note:</strong> If you've already authenticated but still see "Not Connected",
                    click the <strong>"Refresh"</strong> button above.
                  </Alert>
                </Grid>
              )}
            </>
          )}

          <Grid item xs={12} md={6}>
            <TextField fullWidth label="Sync Interval (minutes)" name="sync_interval" value={form.sync_interval} onChange={handleChange} />
          </Grid>
        </Grid>

        <Stack direction="row" spacing={2} sx={{ mt: 3 }}>
          <Button variant="contained" onClick={handleSave}>Save Settings</Button>
        </Stack>

        <input
          ref={folderInputRef}
          type="file"
          webkitdirectory=""
          directory=""
          style={{ display: 'none' }}
          onChange={handleFolderSelected}
        />
      </CardContent>
    </Card>
  );
}

export default Settings;