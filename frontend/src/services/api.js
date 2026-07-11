import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://cctv-backup.onrender.com/api';

// Token storage for cross-site auth
let authToken = null;

// Initialize axios with auth token if available
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  withCredentials: true,  // Required for session-based auth
});

// Add request interceptor to include auth token
api.interceptors.request.use((config) => {
  if (authToken) {
    config.headers.Authorization = `Bearer ${authToken}`;
  }
  return config;
});

// Token management functions
export const setAuthToken = (token) => {
  authToken = token;
};

export const getAuthToken = () => {
  return authToken;
};

export const getHealth = () => api.get('/health');
export const getStats = () => api.get('/stats');
export const startSync = () => api.post('/sync/start');
export const getConfig = () => api.get('/config');
export const saveConfig = (payload) => api.post('/config', payload);
export const getProtocol = () => api.get('/protocol');
export const saveProtocol = (protocolType) => api.post('/protocol', { protocol_type: protocolType });
export const getUploads = (params = {}) => api.get('/uploads', { params });
export const getLogs = (params = {}) => api.get('/logs', { params });
export const getCameras = () => api.get('/cameras');
export const getOnvifRecordings = (params = {}) => api.get('/onvif/recordings', { params });
export const getOnvifSdInfo = () => api.get('/onvif/sd-info');
export const startOnvifSync = () => api.post('/onvif/sync');
export const deleteOnvifRecording = (recordingToken) => api.post('/onvif/delete', { recording_token: recordingToken });
export const browseFolder = () => api.get('/folder/browse');

// Google Drive OAuth endpoints (session-based)
export const getDriveAuthUrl = () => api.get('/drive/auth/url');
export const getDriveAuthStatus = () => api.get('/drive/auth/status');
export const logoutDrive = () => api.post('/drive/auth/logout');

// Session-based OAuth endpoints (using client_secrets.json)
export const connectDrive = () => {
  const BASE_URL = process.env.REACT_APP_API_URL?.replace('/api', '') || 'https://cctv-backup.onrender.com';
  // Force Google to show consent screen and NOT use cached scopes
  const authUrl = `${BASE_URL}/api/drive/auth?include_granted_scopes=false&prompt=consent`;
  window.open(authUrl, 'Connect Google Drive', 'width=500,height=600');
};
export const checkDriveStatus = () => api.get('/drive/status');
export const disconnectDrive = () => api.post('/drive/disconnect');