# Demo

A five-minute walkthrough and a 60–90 second video plan. Both assume the seeded demo
(`make data pipeline migrate seed`, then `make api` and `make web`). Every number below is what
that seed produces. If you change the seed or the model, re-check the numbers before recording.

## The story in one line

Twenty fictional aircraft fly real NASA-simulated engines. The model says which engines will run
out of margin before the week's flying is done, and the optimizer finds the cheapest week of
hangar work that keeps them flying.

## Walkthrough (about 5 minutes)

1. **Overview** (`/overview`). Five engines are critical and one needs review.
   *Schedule exposure* compares each engine's lower-bound RUL (bar) with the cycles it is scheduled
   to fly this week (tick). ENG-802 is scheduled for 28 more cycles than its lower bound allows.
   Point at the **SIMULATION** badge: the airline is fictional, the engine data is NASA's.
2. **Engine ENG-802** (click it). RUL estimate 5.6 cycles, 90% interval 0–13.9. The chart shows
   the prediction falling through the engine's real C-MAPSS history, then projected forward
   through its scheduled legs. Sensor panels are raw NASA readings. Provenance names the test unit
   it came from, and the true RUL, which is only available because this is evaluation data.
3. **Buffer** (top right, set to 40). Ten engines are flagged now instead of six. The flagged
   departures and the maintenance plan follow the buffer, which shows the policy is a choice, not
   a fact of the data.
4. **Flights** (`/flights`). Flagged legs are marked. Filter to aircraft 802 and open the rotation
   view to see where in the week the threshold falls.
5. **Maintenance** (`/maintenance`). The baseline (earliest-due-date) calendar across ORD, DEN and
   ATL bays, with local night shifts shaded. Amber bars started after the engine passed its
   threshold. Click a bar to see its cancelled legs, which link back to the flight schedule.
6. **Scenarios** (`/scenarios`). Run **Default week**. CP-SAT proves an optimal plan in about
   0.1 s: cost 3,514 → 3,102 (−12%), cancelled legs 23 → 19. The job table highlights each move,
   e.g. ENG-816's borescope moved four days later into a ground gap, cancelling no legs instead of 4.
7. Run **DEN bay out**: cancelled legs 23 → 16. The optimizer gives up a few cycles past threshold
   to save legs, and the cost weights decide that trade (they are listed in the assumptions doc).
8. Run **Hard threshold, DEN bay out**. Both methods fail, and the optimizer says why: ENG-802 and
   ENG-808 both need the single DEN bay before 13:45Z. That is a minimal conflict set, not a
   generic "infeasible".
9. **Methodology** (`/methodology`). Test-set metrics (RMSE 11.44 vs 43.24 for the constant
   baseline), interval coverage, and what the model can and cannot claim.

## Video plan (60–90 s, no narration needed; captions in brackets)

| Time | Screen | Caption |
|---|---|---|
| 0–8 s | Overview, slow pan down the exposure chart | [NASA engine simulations, flown by a fictional airline] |
| 8–20 s | Click ENG-802; chart and interval | [RUL 5.6 cycles, 28 scheduled. It won't make the week.] |
| 20–28 s | Change buffer 10 → 40 on overview | [The safety buffer is a policy choice] |
| 28–42 s | Maintenance calendar; click a bar, follow a cancelled-leg link | [Every hangar slot costs flights] |
| 42–60 s | Scenarios: Default week → comparison table | [CP-SAT vs heuristic: −12% cost, proven optimal in 0.1 s] |
| 60–75 s | Hard threshold, DEN bay out → explanation | [When it can't be done, it says exactly why] |
| 75–85 s | Methodology metrics table | [Measured on NASA's held-out test set] |

Recording: 1440×900 browser window, dark UI as shipped, 30 fps. Reseed first (`make seed`) so the
recent-scenarios list is empty.
