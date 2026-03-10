# Debug Session: b2-backup-stalled

**Summary:** Backups to B2 were not uploading until a server restart; it was "blocked" (se blocase) and needed a server restart.

## Symptoms

- **Expected Behavior:** Backups should be uploaded to B2 automatically.
- **Actual Behavior:** Backups were not uploading before the restart.
- **Errors:** None seen by the user.
- **Timeline:** Occurred recently, resolved by a server restart.
- **Reproduction:** No known steps yet.

## Hypotheses

1. The backup job queue (Bull/Redis) was stalled.
2. The B2 service was unavailable or the API was hung.
3. The backend container was in a bad state (resource leak, etc.).
4. Network issues on the server prevented B2 communication.

## Investigation Steps

- [ ] Check current status of the backup queue.
- [ ] Check backend logs for any past errors (even if the user missed them).
- [ ] Verify if new backups are currently being uploaded correctly after the restart.
- [ ] Check if the backup worker is running in the background.

## Evidence
(To be filled during investigation)
