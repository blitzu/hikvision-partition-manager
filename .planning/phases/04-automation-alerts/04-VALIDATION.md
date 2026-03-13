---
phase: 04
slug: automation-alerts
status: validated
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-13
---

# Phase 04 — Validation Strategy

> Per-phase validation contract. Reconstructed from artifacts (State B) + gap-fill audit (2026-03-13).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python3 -m pytest tests/test_jobs_auto_rearm.py tests/test_jobs_monitors.py -x -q` |
| **Full suite command** | `python3 -m pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_jobs_auto_rearm.py tests/test_jobs_monitors.py -x -q`
- **After every plan wave:** Run `python3 -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | JOB-01: schedule_rearm called from disarm_partition | integration | `python3 -m pytest tests/test_disarm.py::test_disarm_calls_schedule_rearm_when_auto_rearm_minutes_set -x -q` | ✅ | ✅ green |
| 04-01-02 | 01 | 1 | JOB-01: cancel_rearm called from arm_partition | integration | `python3 -m pytest tests/test_arm.py::test_arm_calls_cancel_rearm -x -q` | ✅ | ✅ green |
| 04-01-03 | 01 | 1 | JOB-01: schedule_rearm adds job with correct ID | unit | `python3 -m pytest tests/test_jobs_auto_rearm.py::test_schedule_rearm_adds_job_with_correct_id -x -q` | ✅ | ✅ green |
| 04-01-04 | 01 | 1 | JOB-01: schedule_rearm uses ConflictPolicy.replace | unit | `python3 -m pytest tests/test_jobs_auto_rearm.py::test_schedule_rearm_replaces_existing_job -x -q` | ✅ | ✅ green |
| 04-01-05 | 01 | 1 | JOB-01: cancel_rearm removes schedule by correct ID | unit | `python3 -m pytest tests/test_jobs_auto_rearm.py::test_cancel_rearm_removes_schedule_by_correct_id -x -q` | ✅ | ✅ green |
| 04-01-06 | 01 | 1 | JOB-01: cancel_rearm is no-op when schedule missing | unit | `python3 -m pytest tests/test_jobs_auto_rearm.py::test_cancel_rearm_no_op_when_schedule_not_found -x -q` | ✅ | ✅ green |
| 04-01-07 | 01 | 1 | JOB-01: startup reconciliation re-registers missing schedules | unit | `python3 -m pytest tests/test_jobs_auto_rearm.py::test_reconcile_missed_rearm_jobs_re_registers_missing_schedules -x -q` | ✅ | ✅ green |
| 04-01-08 | 01 | 1 | JOB-01: startup reconciliation skips existing schedules | unit | `python3 -m pytest tests/test_jobs_auto_rearm.py::test_reconcile_missed_rearm_jobs_skips_existing_schedules -x -q` | ✅ | ✅ green |
| 04-01-09 | 01 | 1 | ALRT-01: auto_rearm_job calls arm_partition with system:auto_rearm | unit | `python3 -m pytest tests/test_jobs_auto_rearm.py::test_auto_rearm_job_calls_arm_partition_with_system_performed_by -x -q` | ✅ | ✅ green |
| 04-01-10 | 01 | 1 | ALRT-01: auto_rearm_job fires webhook as asyncio.create_task | unit | `python3 -m pytest tests/test_jobs_auto_rearm.py::test_auto_rearm_job_fires_webhook_as_task -x -q` | ✅ | ✅ green |
| 04-01-11 | 01 | 1 | ALRT-01: deliver_webhook succeeds on first attempt | unit | `python3 -m pytest tests/test_jobs_auto_rearm.py::test_deliver_webhook_succeeds_on_first_attempt -x -q` | ✅ | ✅ green |
| 04-01-12 | 01 | 1 | ALRT-01: deliver_webhook retries on failure and succeeds | unit | `python3 -m pytest tests/test_jobs_auto_rearm.py::test_deliver_webhook_retries_on_failure_and_succeeds -x -q` | ✅ | ✅ green |
| 04-01-13 | 01 | 1 | ALRT-01: deliver_webhook gives up after 3 retries (4 total attempts) | unit | `python3 -m pytest tests/test_jobs_auto_rearm.py::test_deliver_webhook_gives_up_after_3_retries -x -q` | ✅ | ✅ green |
| 04-01-14 | 01 | 1 | ALRT-01: deliver_webhook no-op when URL not configured | unit | `python3 -m pytest tests/test_jobs_auto_rearm.py::test_deliver_webhook_no_op_when_url_not_configured -x -q` | ✅ | ✅ green |
| 04-02-01 | 02 | 2 | JOB-02: stuck-disarmed monitor registered with IntervalTrigger(minutes=5) | unit | `python3 -m pytest tests/test_jobs_monitors.py::test_lifespan_registers_stuck_disarmed_monitor_with_5_minute_interval -x -q` | ✅ | ✅ green |
| 04-02-02 | 02 | 2 | JOB-03: NVR health check registered with IntervalTrigger(seconds=60) | unit | `python3 -m pytest tests/test_jobs_monitors.py::test_lifespan_registers_nvr_health_check_with_60_second_interval -x -q` | ✅ | ✅ green |
| 04-02-03 | 02 | 2 | JOB-02/ALRT-02: stuck-disarmed monitor fires webhook for overdue partition | unit | `python3 -m pytest tests/test_jobs_monitors.py::test_stuck_disarmed_monitor_fires_webhook_for_overdue_partition -x -q` | ✅ | ✅ green |
| 04-02-04 | 02 | 2 | JOB-02: stuck-disarmed monitor skips non-overdue partition | unit | `python3 -m pytest tests/test_jobs_monitors.py::test_stuck_disarmed_monitor_skips_non_overdue_partition -x -q` | ✅ | ✅ green |
| 04-02-05 | 02 | 2 | JOB-02: stuck-disarmed monitor skips partitions without alert threshold | unit | `python3 -m pytest tests/test_jobs_monitors.py::test_stuck_disarmed_monitor_skips_partitions_without_alert_threshold -x -q` | ✅ | ✅ green |
| 04-02-06 | 02 | 2 | JOB-02/ALRT-02: stuck-disarmed fires multiple webhooks per cycle | unit | `python3 -m pytest tests/test_jobs_monitors.py::test_stuck_disarmed_monitor_fires_multiple_webhooks_per_cycle -x -q` | ✅ | ✅ green |
| 04-02-07 | 02 | 2 | JOB-03/ALRT-03: NVR health check fires nvr_offline on first failure | unit | `python3 -m pytest tests/test_jobs_monitors.py::test_nvr_health_check_fires_nvr_offline_on_first_failure -x -q` | ✅ | ✅ green |
| 04-02-08 | 02 | 2 | ALRT-03: NVR health check suppresses offline within cooldown | unit | `python3 -m pytest tests/test_jobs_monitors.py::test_nvr_health_check_suppresses_offline_within_cooldown -x -q` | ✅ | ✅ green |
| 04-02-09 | 02 | 2 | ALRT-03: NVR health check fires offline again after cooldown expires | unit | `python3 -m pytest tests/test_jobs_monitors.py::test_nvr_health_check_fires_offline_again_after_cooldown_expires -x -q` | ✅ | ✅ green |
| 04-02-10 | 02 | 2 | ALRT-03: NVR health check fires nvr_online on recovery | unit | `python3 -m pytest tests/test_jobs_monitors.py::test_nvr_health_check_fires_nvr_online_on_recovery -x -q` | ✅ | ✅ green |
| 04-02-11 | 02 | 2 | JOB-03: NVR health check no webhook when stable online | unit | `python3 -m pytest tests/test_jobs_monitors.py::test_nvr_health_check_no_webhook_when_stable_online -x -q` | ✅ | ✅ green |
| 04-02-12 | 02 | 2 | JOB-03: NVR health check updates last_seen_at on success | unit | `python3 -m pytest tests/test_jobs_monitors.py::test_nvr_health_check_updates_last_seen_at_on_success -x -q` | ✅ | ✅ green |
| 04-02-13 | 02 | 2 | JOB-03: NVR health check commits after all NVRs processed | unit | `python3 -m pytest tests/test_jobs_monitors.py::test_nvr_health_check_commits_after_all_nvrs_processed -x -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-03-13

---

## Validation Audit 2026-03-13

| Metric | Count |
|--------|-------|
| Gaps found | 4 |
| Resolved | 4 |
| Escalated | 0 |
