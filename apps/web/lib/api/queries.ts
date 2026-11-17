"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiGet, type QueryValue } from "./client";
import {
  airports,
  engineDetail,
  engineHistory,
  enginePage,
  fleetSummary,
  flightPage,
  modelMetrics,
} from "./schemas";

export function useFleetSummary(buffer: number | undefined) {
  return useQuery({
    queryKey: ["fleet-summary", buffer],
    queryFn: ({ signal }) => apiGet("/api/v1/fleet/summary", fleetSummary, { buffer }, signal),
    placeholderData: keepPreviousData,
  });
}

export function useEngines(params: Record<string, QueryValue>) {
  return useQuery({
    queryKey: ["engines", params],
    queryFn: ({ signal }) => apiGet("/api/v1/engines", enginePage, params, signal),
    placeholderData: keepPreviousData,
  });
}

export function useEngine(id: string, buffer: number | undefined) {
  return useQuery({
    queryKey: ["engine", id, buffer],
    queryFn: ({ signal }) =>
      apiGet(`/api/v1/engines/${encodeURIComponent(id)}`, engineDetail, { buffer }, signal),
    placeholderData: keepPreviousData,
  });
}

export function useEngineHistory(id: string) {
  return useQuery({
    queryKey: ["engine-history", id],
    queryFn: ({ signal }) =>
      apiGet(`/api/v1/engines/${encodeURIComponent(id)}/history`, engineHistory, {}, signal),
    staleTime: Infinity,
  });
}

export function useFlights(params: Record<string, QueryValue>) {
  return useQuery({
    queryKey: ["flights", params],
    queryFn: ({ signal }) => apiGet("/api/v1/flights", flightPage, params, signal),
    placeholderData: keepPreviousData,
  });
}

export function useAirports() {
  return useQuery({
    queryKey: ["airports"],
    queryFn: ({ signal }) => apiGet("/api/v1/airports", airports, {}, signal),
    staleTime: Infinity,
  });
}

export function useModelMetrics() {
  return useQuery({
    queryKey: ["model-metrics"],
    queryFn: ({ signal }) => apiGet("/api/v1/models/metrics", modelMetrics, {}, signal),
    staleTime: Infinity,
  });
}
