import { useMutation, useQuery } from '@tanstack/react-query';
import * as api from '../api/client';

export function usePortfolio(id: string) {
  return useQuery({
    queryKey: ['portfolio', id],
    queryFn: () => api.getPortfolio(id),
    enabled: Boolean(id),
  });
}

export function useTrades(id: string, page = 1, limit = 50) {
  return useQuery({
    queryKey: ['trades', id, page, limit],
    queryFn: () => api.getTrades(id, page, limit),
    enabled: Boolean(id),
  });
}

export function useAnalytics(id: string) {
  return useQuery({
    queryKey: ['analytics', id],
    queryFn: () => api.getAnalytics(id),
    retry: false,
    enabled: Boolean(id),
  });
}

export function useInsights(id: string) {
  return useQuery({
    queryKey: ['insights', id],
    queryFn: () => api.getInsights(id),
    retry: false,
    enabled: Boolean(id),
  });
}

export function useAnalyze(id: string) {
  return useMutation({ mutationFn: () => api.analyzePortfolio(id) });
}

export function useUpload() {
  return useMutation({
    mutationFn: ({ file, name }: { file: File; name?: string }) =>
      api.uploadPortfolio(file, name),
  });
}

export function useProgress(id: string, previousPortfolioId: string) {
  return useQuery({
    queryKey: ['progress', id, previousPortfolioId],
    queryFn: () => api.getProgress(id, previousPortfolioId),
    retry: false,
    enabled: Boolean(id && previousPortfolioId),
  });
}
