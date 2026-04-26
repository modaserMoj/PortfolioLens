import axios from 'axios';
import type {
  UploadResponse,
  Portfolio,
  Trade,
  FullAnalytics,
  InsightData,
  ProgressData,
} from '../types';

const api = axios.create({ baseURL: '/api', timeout: 120_000 });

export async function uploadPortfolio(
  file: File,
  name?: string,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  if (name) form.append('name', name);
  const { data } = await api.post<UploadResponse>('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function getPortfolio(id: string): Promise<Portfolio> {
  const { data } = await api.get<Portfolio>(`/portfolio/${id}`);
  return data;
}

export async function getTrades(
  id: string,
  page = 1,
  limit = 50,
): Promise<{ trades: Trade[]; total: number; page: number }> {
  const { data } = await api.get(`/portfolio/${id}/trades`, {
    params: { page, limit },
  });
  return data;
}

export async function analyzePortfolio(id: string): Promise<{ status: string }> {
  const { data } = await api.post(`/portfolio/${id}/analyze`);
  return data;
}

export async function getAnalytics(id: string): Promise<FullAnalytics> {
  const { data } = await api.get<FullAnalytics>(`/portfolio/${id}/analytics`);
  return data;
}

export async function getInsights(id: string): Promise<InsightData> {
  const { data } = await api.get<InsightData>(`/portfolio/${id}/insights`);
  return data;
}

export async function getProgress(
  id: string,
  previousPortfolioId: string,
): Promise<ProgressData> {
  const { data } = await api.get<ProgressData>(`/portfolio/${id}/progress`, {
    params: { previous_portfolio_id: previousPortfolioId },
  });
  return data;
}
