# Interface registry

## Public dossier exports

### `GET /api/projects/{project_id}`
Allowlisted public dossier projection containing only public project, claim, response and gap fields.

### `GET /api/projects/{project_id}/report`
Markdown evidence report for the public dossier.

### `GET /api/projects/{project_id}/rti`
Draft RTI export for the public dossier.

### `GET /api/projects/{project_id}/capsule`
Deterministic JSON evidence capsule for the public dossier.

The capsule includes:
- allowlisted public dossier fields
- evidence envelopes derived from published claims
- deterministic `capsule_sha256`
- methodology statements for verification and non-overclaim boundaries

Verify downloaded capsules with:

```bash
python3 scripts/verify_capsule.py capsule.json
```
