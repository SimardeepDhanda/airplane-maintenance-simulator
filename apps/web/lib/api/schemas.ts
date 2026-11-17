import { z } from "zod";

export const planningStatus = z.enum(["ok", "review", "critical"]);
export type PlanningStatus = z.infer<typeof planningStatus>;

export const errorEnvelope = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.array(z.record(z.string(), z.unknown())).optional(),
  }),
});

const page = <T extends z.ZodType>(item: T) =>
  z.object({ items: z.array(item), total: z.number(), page: z.number(), page_size: z.number() });

export const prediction = z.object({
  rul_point: z.number(),
  rul_lower: z.number(),
  rul_upper: z.number(),
  model_version: z.string(),
  observed_through_cycle: z.number(),
});

export const planning = z.object({
  forecast_legs: z.number(),
  forecast_cycles: z.number(),
  margin: z.number(),
  conservative_margin: z.number(),
  status: planningStatus,
  buffer: z.number(),
  first_flagged_flight_id: z.string().nullable(),
  first_flagged_departure: z.string().nullable(),
});

export const engineSummary = z.object({
  id: z.string(),
  aircraft_id: z.string().nullable(),
  station: z.string().nullable(),
  observed_cycles: z.number(),
  prediction,
  planning,
});
export type EngineSummary = z.infer<typeof engineSummary>;
export const enginePage = page(engineSummary);

export const flight = z.object({
  id: z.string(),
  flight_number: z.string(),
  aircraft_id: z.string(),
  engine_id: z.string().nullable(),
  origin: z.string(),
  destination: z.string(),
  departure: z.string(),
  arrival: z.string(),
  departure_local: z.string(),
  arrival_local: z.string(),
  origin_tz: z.string(),
  destination_tz: z.string(),
  origin_tz_abbr: z.string(),
  destination_tz_abbr: z.string(),
  status: z.string(),
  cycles: z.number(),
  cumulative_cycles: z.number(),
  conservative_margin_after: z.number().nullable(),
  flagged: z.boolean(),
});
export type Flight = z.infer<typeof flight>;
export const flightPage = page(flight);

export const engineDetail = engineSummary.extend({
  fleet_type: z.string().nullable(),
  home_base: z.string().nullable(),
  provenance: z.object({
    dataset: z.string(),
    subset: z.string(),
    split: z.string(),
    unit_id: z.number(),
    data_kind: z.string(),
    eval_true_rul: z.number().nullable(),
  }),
  flights: z.array(flight),
});
export type EngineDetail = z.infer<typeof engineDetail>;

export const engineHistory = z.object({
  engine_id: z.string(),
  model_version: z.string(),
  cycles: z.array(z.number()),
  sensors: z.array(z.object({ name: z.string(), values: z.array(z.number()) })),
  rul_point: z.array(z.number()),
  rul_lower: z.array(z.number()),
  rul_upper: z.array(z.number()),
});
export type EngineHistory = z.infer<typeof engineHistory>;

export const modelRef = z.object({
  version: z.string(),
  data_kind: z.string(),
  subset: z.string(),
  trained_at: z.string(),
});

export const fleetSummary = z.object({
  as_of: z.string(),
  horizon_end: z.string(),
  aircraft: z.number(),
  engines: z.number(),
  flights: z.number(),
  planning_buffer: z.number(),
  status_counts: z.object({ ok: z.number(), review: z.number(), critical: z.number() }),
  model: modelRef,
});
export type FleetSummary = z.infer<typeof fleetSummary>;

export const airport = z.object({
  code: z.string(),
  name: z.string(),
  city: z.string(),
  timezone: z.string(),
  is_hub: z.boolean(),
  has_maintenance_base: z.boolean(),
});
export type Airport = z.infer<typeof airport>;
export const airports = z.array(airport);

const scores = z.object({
  rmse: z.number(),
  mae: z.number(),
  rmse_vs_capped_truth: z.number(),
  mae_vs_capped_truth: z.number(),
  bias: z.number(),
  phm08_score: z.number(),
});

const coverage = z.object({
  coverage: z.number(),
  lower_bound_coverage: z.number(),
  mean_width: z.number(),
  n: z.number(),
});

export const modelMetrics = z.object({
  model: modelRef,
  selection: z.object({
    metric: z.string(),
    cv: z.string(),
    results: z.array(scores.extend({ model: z.string(), target_cap: z.number().nullable() })),
    selected: z.object({ model: z.string(), target_cap: z.number().nullable() }),
  }),
  test: z.object({
    n_engines: z.number(),
    n_rows: z.number(),
    comparison: z.array(
      z.object({
        model: z.string(),
        target_cap: z.number().nullable(),
        selected: z.boolean(),
        last_cycle: scores,
        all_cycles: scores,
      }),
    ),
    selected_by_true_rul_bin: z.array(
      z.object({
        true_rul: z.string(),
        n: z.number(),
        rmse: z.number(),
        mae: z.number(),
        bias: z.number(),
      }),
    ),
    intervals: z.object({
      nominal_coverage: z.number(),
      last_cycle: coverage,
      all_cycles: coverage,
    }),
    per_engine: z.array(
      z.object({
        unit_id: z.number(),
        observed_cycles: z.number(),
        true_rul: z.number(),
        rul_point: z.number(),
        rul_lower: z.number(),
        rul_upper: z.number(),
      }),
    ),
    trajectories: z.array(
      z.object({
        unit_id: z.number(),
        cycle: z.array(z.number()),
        true_rul: z.array(z.number()),
        rul_point: z.array(z.number()),
        rul_lower: z.array(z.number()),
        rul_upper: z.array(z.number()),
      }),
    ),
  }),
  permutation_importance: z.object({
    data: z.string(),
    features: z.array(z.object({ feature: z.string(), mean: z.number(), std: z.number() })),
  }),
  features: z.object({
    sensors: z.array(z.string()),
    dropped_channels: z.array(z.string()),
    window: z.number(),
    baseline_cycles: z.number(),
  }),
  conformal: z.object({
    alpha: z.number(),
    bin_edges: z.array(z.number()),
    lower_offsets: z.array(z.number().nullable()),
    upper_offsets: z.array(z.number().nullable()),
  }),
  split: z.object({ fit_units: z.array(z.number()), calibration_units: z.array(z.number()) }),
});
export type ModelMetrics = z.infer<typeof modelMetrics>;

// --- Maintenance planning ---

export const jobType = z.enum(["engine_change", "borescope"]);
export type JobType = z.infer<typeof jobType>;
export const methodStatus = z.enum(["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "NO_SOLUTION"]);
export type MethodStatus = z.infer<typeof methodStatus>;

export const maintenanceResources = z.object({
  horizon_start: z.string(),
  horizon_end: z.string(),
  facilities: z.array(
    z.object({
      code: z.string(),
      name: z.string(),
      kind: z.enum(["hangar", "line"]),
      timezone: z.string(),
      supports: z.array(jobType),
      bays: z.array(z.object({ id: z.string(), name: z.string() })),
      shifts: z.array(
        z.object({
          name: z.string(),
          start_local: z.string(),
          end_local: z.string(),
          technicians: z.number(),
          is_night: z.boolean(),
        }),
      ),
    }),
  ),
  parts: z.array(
    z.object({
      id: z.string(),
      part_type: z.string(),
      location: z.string(),
      quantity: z.number(),
      available_at: z.string(),
      transfer_lead_hours: z.number(),
    }),
  ),
  job_types: z.array(
    z.object({
      id: jobType,
      label: z.string(),
      duration_hours: z.number(),
      technicians: z.number(),
      part_type: z.string().nullable(),
    }),
  ),
});
export type MaintenanceResources = z.infer<typeof maintenanceResources>;

export const job = z.object({
  id: z.string(),
  engine_id: z.string().nullable(),
  aircraft_id: z.string(),
  job_type: jobType,
  reason: z.enum(["critical", "review", "added"]),
  duration_hours: z.number(),
  technicians: z.number(),
  part_type: z.string().nullable(),
  due_flight_id: z.string().nullable(),
  due_at: z.string().nullable(),
});
export type Job = z.infer<typeof job>;

export const placement = z.object({
  job_id: z.string(),
  engine_id: z.string().nullable(),
  aircraft_id: z.string(),
  job_type: jobType,
  reason: z.string(),
  facility: z.string(),
  bay: z.string(),
  start: z.string(),
  end: z.string(),
  start_local: z.string(),
  end_local: z.string(),
  tz_abbr: z.string(),
  cancelled_flights: z.array(z.string()),
  cycles_over: z.number(),
  part_lot: z.string().nullable(),
  part_from: z.string().nullable(),
  labor_hours: z.number(),
  why: z.array(z.string()),
});
export type PlacementT = z.infer<typeof placement>;

export const plan = z.object({
  method: z.enum(["baseline", "optimized"]),
  status: methodStatus,
  objective: z.number().nullable(),
  best_bound: z.number().nullable(),
  wall_ms: z.number(),
  costs: z
    .object({
      cancellations: z.number(),
      threshold: z.number(),
      unscheduled: z.number(),
      labor: z.number(),
      transfers: z.number(),
      total: z.number(),
    })
    .nullable(),
  metrics: z
    .object({
      jobs_total: z.number(),
      jobs_scheduled: z.number(),
      jobs_unscheduled: z.number(),
      thresholds_missed: z.number(),
      cycles_over_threshold: z.number(),
      cancelled_legs: z.number(),
      grounded_legs: z.number(),
      labor_hours: z.number(),
      part_transfers: z.number(),
      bay_utilization: z.number(),
    })
    .nullable(),
  placements: z.array(placement),
  unscheduled: z.array(
    z.object({
      job_id: z.string(),
      engine_id: z.string().nullable(),
      aircraft_id: z.string(),
      job_type: jobType,
      reason: z.string(),
      cycles_over: z.number(),
      why: z.string(),
    }),
  ),
  explanations: z.array(
    z.object({ job_id: z.string().nullable(), code: z.string(), message: z.string() }),
  ),
  verified: z.boolean(),
  jobs: z.array(job),
});
export type Plan = z.infer<typeof plan>;

export const assumptions = z.object({
  buffer: z.number(),
  threshold_policy: z.enum(["penalty", "hard"]),
  bay_changes: z.record(z.string(), z.number()),
  part_delay_hours: z.number(),
  grounded_aircraft: z.array(z.string()),
  added_jobs: z.array(z.object({ aircraft_id: z.string(), job_type: jobType })),
  time_limit_s: z.number(),
});
export type Assumptions = z.infer<typeof assumptions>;

export const scenarioStatus = z.enum(["created", "queued", "running", "solved", "failed"]);

export const scenario = z.object({
  id: z.number(),
  name: z.string(),
  status: scenarioStatus,
  error: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  assumptions,
  baseline: plan.nullable(),
  optimized: plan.nullable(),
  comparison: z.array(
    z.object({
      key: z.string(),
      label: z.string(),
      unit: z.string(),
      baseline: z.number().nullable(),
      optimized: z.number().nullable(),
      delta: z.number().nullable(),
      pct_change: z.number().nullable(),
      better: z.enum(["lower", "higher"]).nullable(),
    }),
  ),
});
export type Scenario = z.infer<typeof scenario>;

export const scenarioList = z.array(
  z.object({
    id: z.number(),
    name: z.string(),
    status: z.string(),
    created_at: z.string(),
    baseline_status: z.string().nullable(),
    optimized_status: z.string().nullable(),
  }),
);
