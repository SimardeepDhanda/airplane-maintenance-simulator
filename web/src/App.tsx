import { useEffect, useMemo, useState } from "react";
import { DAYS, dueDay, flightsLost, schedule, type Engine } from "./schedule";
import RulChart from "./RulChart";

type Fleet = {
  scores: { model_rmse: number; model_mae: number; baseline_rmse: number; test_engines: number };
  rul_cap: number;
  engines: Engine[];
};

export default function App() {
  const [fleet, setFleet] = useState<Fleet | null>(null);
  const [bays, setBays] = useState(1);
  const [buffer, setBuffer] = useState(10);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    fetch("/fleet.json")
      .then((r) => r.json())
      .then((data: Fleet) => {
        setFleet(data);
        const soonest = [...data.engines].sort((a, b) => a.predicted_rul - b.predicted_rul)[0];
        setSelected(soonest.tail);
      });
  }, []);

  const jobs = useMemo(
    () => (fleet ? schedule(fleet.engines, bays, buffer) : []),
    [fleet, bays, buffer],
  );

  if (!fleet) return <p className="loading">Loading…</p>;

  const jobFor = (tail: string) => jobs.find((j) => j.tail === tail);
  const engine = fleet.engines.find((e) => e.tail === selected);
  const engines = [...fleet.engines].sort((a, b) => dueDay(a, buffer) - dueDay(b, buffer));
  const late = jobs.filter((j) => j.late).length;

  return (
    <main>
      <header>
        <h1>AeroFleet</h1>
        <p>
          Predicts how many more flights each engine has left, then fits the ones that are running
          out into the hangar over the next two weeks. Engine data is from NASA's C-MAPSS turbofan
          simulation; the airline is made up.
        </p>
      </header>

      <section className="controls">
        <label>
          Hangar bays
          <input type="range" min={1} max={3} value={bays} onChange={(e) => setBays(+e.target.value)} />
          <b>{bays}</b>
        </label>
        <label>
          Safety buffer
          <input type="range" min={0} max={40} step={5} value={buffer} onChange={(e) => setBuffer(+e.target.value)} />
          <b>{buffer} cycles</b>
        </label>
        <span className="summary">
          {jobs.length} engine changes, {late} late, {flightsLost(jobs, fleet.engines)} flights lost
        </span>
      </section>

      <section>
        <h2>Hangar, next {DAYS} days</h2>
        <div className="calendar" style={{ gridTemplateColumns: `4rem repeat(${DAYS}, 1fr)` }}>
          <div />
          {Array.from({ length: DAYS }, (_, d) => (
            <div key={d} className="day">Day {d + 1}</div>
          ))}
          {Array.from({ length: bays }, (_, bay) => (
            <Row key={bay} bay={bay} jobs={jobs} selected={selected} onSelect={setSelected} />
          ))}
        </div>
        {jobs.some((j) => j.day === null) && (
          <p className="warn">
            No room for {jobs.filter((j) => j.day === null).map((j) => j.tail).join(", ")} in the
            next {DAYS} days.
          </p>
        )}
      </section>

      <div className="split">
        <section>
          <h2>Fleet</h2>
          <table>
            <thead>
              <tr>
                <th>Plane</th>
                <th>Flights/day</th>
                <th>Cycles left</th>
                <th>Due</th>
                <th>Hangar</th>
              </tr>
            </thead>
            <tbody>
              {engines.map((e) => {
                const job = jobFor(e.tail);
                return (
                  <tr
                    key={e.tail}
                    className={e.tail === selected ? "selected" : undefined}
                    onClick={() => setSelected(e.tail)}
                  >
                    <td>{e.tail}</td>
                    <td>{e.flights_per_day}</td>
                    <td>{e.predicted_rul}</td>
                    <td>{job ? `day ${job.dueDay + 1}` : ""}</td>
                    <td className={job?.late ? "late" : undefined}>
                      {job ? (job.day === null ? "no slot" : `day ${job.day + 1}`) : ""}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>

        {engine && (
          <section>
            <h2>
              {engine.tail} <small>engine {engine.engine}, {engine.cycles_flown} cycles flown</small>
            </h2>
            <RulChart engine={engine} cap={fleet.rul_cap} />
            <p className="note">
              Predicted {engine.predicted_rul} cycles left, actually had {engine.actual_rul}.
            </p>
          </section>
        )}
      </div>

      <footer>
        Model: gradient boosting on rolling sensor averages. On NASA's {fleet.scores.test_engines} test
        engines it's off by {fleet.scores.model_mae} cycles on average (RMSE {fleet.scores.model_rmse},
        vs {fleet.scores.baseline_rmse} for linear regression).
      </footer>
    </main>
  );
}

function Row({ bay, jobs, selected, onSelect }: {
  bay: number;
  jobs: ReturnType<typeof schedule>;
  selected: string | null;
  onSelect: (tail: string) => void;
}) {
  return (
    <>
      <div className="bay">Bay {bay + 1}</div>
      {Array.from({ length: DAYS }, (_, d) => {
        const job = jobs.find((j) => j.day === d && j.bay === bay);
        if (!job) return <div key={d} className="slot" />;
        return (
          <button
            key={d}
            className={`slot job${job.late ? " late" : ""}${job.tail === selected ? " selected" : ""}`}
            onClick={() => onSelect(job.tail)}
            title={job.late ? `due day ${job.dueDay + 1}` : undefined}
          >
            {job.tail}
          </button>
        );
      })}
    </>
  );
}
