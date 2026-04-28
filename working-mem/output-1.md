╭────────────────────────────────────────────────────────────────────╮
│ Working Memory: Context Overflow & Memory Management               │
│ Demonstrating how summarisation solves the finite context problem. │
│ Budget: 4,000 tokens  ·  Model: gemini-2.5-flash  ·  Steps: 10     │
╰────────────────────────────────────────────────────────────────────╯

───────────────────── Phase 1 — Naive Agent (full history, no compression) ─────────────────────

  Step 01  Schema Snapshot               █░░░░░░░░░░░░░░░░░░░  250  (6%)
  Step 02  Row Count & Volume            ██░░░░░░░░░░░░░░░░░░  430  (10%)
  Step 03  Index Inventory               ████░░░░░░░░░░░░░░░░  766  (19%)
  Step 04  Foreign Key Audit             ██████░░░░░░░░░░░░░░  1,132  (28%)
  Step 05  Stored Procedure Audit        ███████░░░░░░░░░░░░░  1,342  (33%)
  Step 06  Application Query Scan        ████████░░░░░░░░░░░░  1,631  (40%)
  Step 07  Staging Test Results          █████████░░░░░░░░░░░  1,781  (44%)
  Step 08  Deployment Checklist          ██████████░░░░░░░░░░  1,954  (48%)
  Step 09  Risk Assessment               ██████████░░░░░░░░░░  2,087  (52%)
  Step 10  Final Sign-Off                █████████████░░░░░░░  2,566  (64%)


-- Verification A: Naive (Full Context) ──────────────────────────────────────

  Model Answer: The exact rollback command documented in the initial schema analysis (Step 1) 
is:
               `pg_restore -d prod snapshot_20240115_pre_migration.dump`  The rollback
               time window is: **4 hours post-migration** (WAL segments are purged after
               that).
  Result: RETAINED (keywords: pg_restore, snapshot_20240115_pre_migration, 4 hours)

-- Verification B: Naive (Overflowed/Truncated) ──────────────────────────────────────

  Model Answer: Based on the information provided across all steps, the **initial schema 
analysis
  Result: LOST (keywords: pg_restore, snapshot_20240115_pre_migration, 4 hours)

─────────────────────── Phase 2 — Managed Agent (summarise after step 5) ───────────────────────

  Step 01  Schema Snapshot               █░░░░░░░░░░░░░░░░░░░  250  (6%)
  Step 02  Row Count & Volume            ██░░░░░░░░░░░░░░░░░░  429  (10%)
  Step 03  Index Inventory               ███░░░░░░░░░░░░░░░░░  592  (14%)
  Step 04  Foreign Key Audit             ████░░░░░░░░░░░░░░░░  891  (22%)
  Step 05  Stored Procedure Audit        █████░░░░░░░░░░░░░░░  1,099  (27%)  ← compressed here

  → Context at 1,099 tokens — compressing steps 1–5...
──────────────────────────── Compression Strategy (Write-to-Memory) ────────────────────────────
  Input: verbose history of 5 steps.
  Goal: dense bullet points, zero information loss.
─────────────────────────────────── Compressed Memory Output ───────────────────────────────────
*   **Schema Snapshot:**
    *   **Tables:**
        *   `users`: `id` INT PK, `email` VARCHAR(

  Context Shift: 1,099 → 58 tokens (94% reduction)

  Step 06  Application Query Scan        █░░░░░░░░░░░░░░░░░░░  222  (5%)
  Step 07  Staging Test Results          ██░░░░░░░░░░░░░░░░░░  374  (9%)
  Step 08  Deployment Checklist          ███░░░░░░░░░░░░░░░░░  549  (13%)
  Step 09  Risk Assessment               ███░░░░░░░░░░░░░░░░░  683  (17%)
  Step 10  Final Sign-Off                ████░░░░░░░░░░░░░░░░  800  (20%)


-- Verification C: Managed (Compressed Memory) ──────────────────────────────────────
  Model Answer: Based on the initial schema analysis (Step 2), the exact rollback command and 
time
               window documented were:  *   **Roll
  Result: LOST (keywords: pg_restore, snapshot_20240115_pre_migration, 4 hours)

─────────────────────────────────────── Overall Summary ────────────────────────────────────────
                      Token Usage Per Step (budget: 4,000)                      
┏━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Step ┃ Name                       ┃    Naive     ┃   Managed    ┃   Saved    ┃
┡━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│  1   │ Schema Snapshot            │     250      │     250      │     —      │
├──────┼────────────────────────────┼──────────────┼──────────────┼────────────┤
│  2   │ Row Count & Volume         │     430      │     429      │     −1     │
├──────┼────────────────────────────┼──────────────┼──────────────┼────────────┤
│  3   │ Index Inventory            │     766      │     592      │    −174    │
├──────┼────────────────────────────┼──────────────┼──────────────┼────────────┤
│  4   │ Foreign Key Audit          │    1,132     │     891      │    −241    │
├──────┼────────────────────────────┼──────────────┼──────────────┼────────────┤
│  5   │ Stored Procedure Audit     │    1,342     │    1,099     │    −243    │
├──────┼────────────────────────────┼──────────────┼──────────────┼────────────┤
│  6   │ Application Query Scan     │    1,631     │     222      │   −1,409   │
├──────┼────────────────────────────┼──────────────┼──────────────┼────────────┤
│  7   │ Staging Test Results       │    1,781     │     374      │   −1,407   │
├──────┼────────────────────────────┼──────────────┼──────────────┼────────────┤
│  8   │ Deployment Checklist       │    1,954     │     549      │   −1,405   │
├──────┼────────────────────────────┼──────────────┼──────────────┼────────────┤
│  9   │ Risk Assessment            │    2,087     │     683      │   −1,404   │
├──────┼────────────────────────────┼──────────────┼──────────────┼────────────┤
│  10  │ Final Sign-Off             │    2,566     │     800      │   −1,766   │
└──────┴────────────────────────────┴──────────────┴──────────────┴────────────┘

      Critical State Retention (Recall of Step 1 Rollback Facts)       
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Scenario                                         ┃      Result      ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ Naive Agent — full history (pass)                │     RETAINED     │
├──────────────────────────────────────────────────┼──────────────────┤
│ Naive Agent — history overflowed (fail)          │       LOST       │
├──────────────────────────────────────────────────┼──────────────────┤
│ Managed Agent — compressed memory (pass)         │       LOST       │
└──────────────────────────────────────────────────┴──────────────────┘

  Verdict: Summarisation was too lossy — critical state not retained.
