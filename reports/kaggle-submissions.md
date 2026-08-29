# Kaggle submission registry

This file links immutable local/GitHub artifacts to Kaggle submission records. Public leaderboard ratings are intentionally excluded until they have converged.

| Kaggle ID | Submitted at (UTC) | Git commit | Environment | Artifact SHA-256 | Description | Validation status |
|---:|---|---|---|---|---|---|
| `55862417` | `2026-08-29 07:47:37` | `b09128d06a049ebde83b18c4c314c66840d0af94` | `kaggle-environments 1.32.7` | `ba3c40d9fb9a2f695b99480063d6a4d8bd3818e6869ae0789add67639fde78be` | `modular agent v1` | `PENDING` |

## Verification policy

- `PENDING` means Kaggle accepted the upload but has not completed its validation episode.
- Change the status to `COMPLETE` only after the Kaggle Submissions page reports success and at least one episode exists.
- If Kaggle reports `ERROR`, download the corresponding agent logs, reproduce the problem locally, and create a new commit rather than rewriting this record.
- The generated `submission.tar.gz` stays untracked; its SHA-256 is the immutable link to the uploaded artifact.
