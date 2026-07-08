import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  withCredentials: true,  // Required for session-based auth
});

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
  // Open Google OAuth popup
  window.open('http://localhost:5000/api/drive/auth', 'Connect Google Drive', 'width=500,height=600');
};
export const checkDriveStatus = () => api.get('/drive/status');
export const disconnectDrive = () => api.post('/drive/disconnect');
