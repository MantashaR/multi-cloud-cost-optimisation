import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export const api = axios.create({ baseURL });

export const getDashboard = () => api.get("/dashboard/").then((r) => r.data);

export const triggerAnalysis = () => api.post("/analysis-runs/trigger/").then((r) => r.data);

export const getAnalysisRun = (id) => api.get(`/analysis-runs/${id}/`).then((r) => r.data);

export const getLatestAnalysisRun = () =>
  api.get("/analysis-runs/latest/").then((r) => r.data).catch(() => null);

export const updateRecommendationStatus = (id, status) =>
  api.patch(`/recommendations/${id}/status_update/`, { status }).then((r) => r.data);

export const terraformDownloadUrl = (id) => `${baseURL}/recommendations/${id}/terraform/`;
