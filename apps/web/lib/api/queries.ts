"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, type QueryValue } from "./client";
import {
  type Assumptions,
  maintenanceResources,
  plan,
  scenario,
  scenarioList,
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

export function useMaintenanceResources() {
  return useQuery({
    queryKey: ["maintenance-resources"],
    queryFn: ({ signal }) =>
      apiGet("/api/v1/maintenance/resources", maintenanceResources, {}, signal),
    staleTime: Infinity,
  });
}

export function useMaintenancePlan(buffer: number | undefined, enabled = true) {
  return useQuery({
    queryKey: ["maintenance-plan", buffer],
    queryFn: ({ signal }) => apiGet("/api/v1/maintenance/plan", plan, { buffer }, signal),
    placeholderData: keepPreviousData,
    enabled,
  });
}

const ACTIVE = new Set(["queued", "running"]);

/** Polls while the scenario is solving. */
export function useScenario(id: number | undefined) {
  const client = useQueryClient();
  return useQuery({
    queryKey: ["scenario", id],
    queryFn: async ({ signal }) => {
      const before = client.getQueryData<{ status: string }>(["scenario", id])?.status;
      const s = await apiGet(`/api/v1/scenarios/${id}`, scenario, {}, signal);
      // The recent list shows status too; refresh it when a solve we were polling finishes.
      if (before && ACTIVE.has(before) && !ACTIVE.has(s.status)) {
        void client.invalidateQueries({ queryKey: ["scenarios"] });
      }
      return s;
    },
    enabled: id !== undefined,
    refetchInterval: (query) => (ACTIVE.has(query.state.data?.status ?? "") ? 750 : false),
  });
}

export function useScenarios() {
  return useQuery({
    queryKey: ["scenarios"],
    queryFn: ({ signal }) => apiGet("/api/v1/scenarios", scenarioList, { limit: 15 }, signal),
  });
}

/** Create a scenario and queue its solve; resolves with the scenario id. */
export function useRunScenario() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: { name?: string; assumptions: Assumptions }) => {
      const created = await apiPost("/api/v1/scenarios", scenario, input);
      const queued = await apiPost(`/api/v1/scenarios/${created.id}/solve`, scenario);
      client.setQueryData(["scenario", created.id], queued);
      return created.id;
    },
    onSettled: () => client.invalidateQueries({ queryKey: ["scenarios"] }),
  });
}
