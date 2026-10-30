# OCI Management Portal Helm Chart

This chart deploys the Flask/Gunicorn OCI Management Portal container on Kubernetes.

## Build and Push the Image

```bash
docker build -t iad.ocir.io/<ocir-namespace>/oci-management-portal:0.1.0 .
docker push iad.ocir.io/<ocir-namespace>/oci-management-portal:0.1.0
```

If your OCIR repository is private, create an image pull secret and reference it in `imagePullSecrets`.

## Configure Values

Start from the example file:

```bash
cp deploy/helm/oci-management-portal/values.example.yaml my-values.yaml
```

Update:

- `image.repository` and `image.tag`
- `config.appUri` with the public URL used by OIDC callbacks
- `config.tagNamespace`, `config.tagKey`, `config.filterKey`, and `config.cleanupCompartment`
- `config.idmEndpoint` and `config.clientId`
- `secret.clientSecret`

The chart defaults to `config.authType=instance_principal`, which uses the OKE worker node instance principal. Create an OCI dynamic group for the worker node instance or node compartment, then grant that dynamic group the required policies. If you use workload principal instead, set `config.authType=workload_principal` and set `serviceAccount.automount=true`. If you use profile auth, set `config.authType=profile`, set `config.configFile`, and mount your OCI config/key with `extraVolumes` and `extraVolumeMounts`.

For more than one replica, set `config.sessionBackend` to `redis` or `valkey` and provide `config.sessionRedisUrl`. Filesystem sessions are only suitable for a single pod.

## Expired Resource Notification

The chart can create a Kubernetes CronJob that publishes a tenancy-wide expired-resource report to an OCI Notifications topic. Every confirmed subscriber receives the same report.

Resources are deduplicated by OCID across regions. Only resources with valid expiry dates before today and a non-empty configured Owner tag are counted. Resources with missing or blank Owner tags are excluded from both the total and ranking. The top 25 expired resources are ranked by cost over the previous 30 complete UTC days, descending. Each entry shows resource name, resource type, compartment name, Owner tag, and cost with currency, in a readable plain-text layout. Compartment names are resolved once per distinct compartment in the displayed list; the signer needs permission to read those compartments. If OCI denies access to a name or the compartment is no longer found, the entry shows its compartment OCID with a name-unavailable label. Resources without cost data remain in the expired count but are excluded from ranking. Billing data can lag; these amounts are not real-time spending rates. Cost API failures fail the job rather than publish a misleading ranking. `filter.py` is unchanged.

The report signer also needs access to the Usage API (for example, an administrator can grant its dynamic group `read usage-report in tenancy`). Costs are queried in the tenancy home region and all response pages are read. Mixed currencies cause the job to fail rather than compare unlike amounts.

The top resources use a compact plain-text table with rank, resource name, type, compartment, Owner, and cost columns. Full values are retained; long rows may wrap on narrow email screens. The existing Notifications publisher sends RAW_TEXT, not a styled HTML table.

Enable it in your values file:

```yaml
expiredResourceReport:
  enabled: true
  schedule: "0 0 * * *"
  regions: ""
  maxItems: 25
  notification:
    topicId: "ocid1.onstopic.oc1..replace_me"
    region: "us-ashburn-1"
    endpoint: ""
    title: "OCI expired resources"
```

The report uses the same tag configuration as the portal:

- `config.tagNamespace` / `config.tagKey` for the Owner tag
- `config.filterNamespace` / `config.filterKey` for the expiry tag
- `config.cleanupCompartment` to exclude cleanup/quarantine resources

The CronJob reuses the portal image, ConfigMap, Secret, and service account. Grant the app signer permission to publish to the Notifications topic.

## Install

### Choose manager or owner reports

The existing `modules.reports.expired_resources_notification` entry point and shared-topic report are unchanged. Set `expiredResourceReport.mode: managers` (the default) to send that report to the configured `notification.topicId`, for example a topic subscribed to by managers. This mode does not infer manager addresses from resource tags.

Set `mode: owners` to run the new `modules.reports.expired_resources_owner_notification` entry point. The chart selects the owner entry point even if an older values file still contains the original `command`. Only one mode runs per release. No extra CronJob is created. Existing in-flight Jobs are not changed by a mode switch; allow them to finish first.

Merge this into your existing values; retain your image, secrets, service-account and application settings:

```yaml
expiredResourceReport:
  enabled: true
  mode: owners
  dryRun: true  # preview first; false enables topic/subscription creation and publishing
  schedule: "0 0 * * *"
  maxItems: 25
  notification:
    region: us-phoenix-1
    title: "OCI expired resources"
    # topicId is only used by managers mode.
  ownerNotifications:
    compartmentId: "ocid1.compartment.oc1..replace_me"
    topicPrefix: gitdash-expiry # project name for new topics; retain existing prefix on upgrades
    allowedEmailDomains: "oracle.com" # optional exact-domain allowlist, comma separated
```

Owner mode searches with the application signer, reuses the expiry/deduplication/cost logic, then groups by normalized email. Both `user@example.com` and `Domain/user@example.com` map to `user@example.com`. Email matching is case-insensitive, but plus aliases are kept distinct. Invalid/ambiguous tags are skipped. It sends each owner only their own count and top 25 table; cost data is queried once per run. Resource Owner tags must be maintained by trusted users because they control who receives resource details.

New owner topics use `<topicPrefix>-<owner-name>`. Set `topicPrefix` to your project name for a new deployment: `gitdash` and `samratha.s.p@oracle.com` produce `gitdash-samratha-s-p`. The owner name is the lowercase email local part, with characters other than letters, digits, underscores, and hyphens replaced by hyphens. Owner names are visible in topic names. Distinct emails that produce the same name are blocked by full owner-hash validation, never combined; resolve such naming conflicts before sending.

Keep your existing prefix on upgrades: legacy `<topicPrefix>-<email-hash>` topics are reused with their current subscriptions, not renamed or duplicated. Changing the prefix changes topic identity and can create another subscription. OCI topic updates do not support renaming; migrating an existing topic to a readable name requires a separately planned replacement and subscription confirmation. If both legacy and readable topics exist for one owner, the job stops that owner's operation for review.

Managed topic tags bind each topic to its owner in the configured region and compartment. Existing arbitrary topics are not adopted, and any unexpected recipient, protocol, duplicate subscription, or ownership marker blocks publication. The subscription list is checked again immediately before publishing. Restrict topic/subscription administration to trusted identities: ONS cannot atomically check recipients and publish, so concurrent subscription changes cannot be made safe by application checks alone.

On first onboarding, the job creates a topic and an EMAIL subscription. OCI sends a confirmation email; the owner must confirm it before delivery. Pending owners are skipped and reconsidered next run. The job does not auto-confirm or repeatedly resend confirmations. Use OCI's resend-confirmation action for expired confirmation links.

Topic lookup is refreshed for each owner. If an operator intentionally deleted a topic, the job waits briefly for deletion to finish before recreating it with a new creation retry token. It checks that the new topic is ACTIVE before creating its subscription against the new OCID. Subscription propagation failures are retried up to seven attempts, ten seconds apart, using the same subscription retry token within that attempt. Logs show creation, waiting, retries, and pending confirmation; persistent API failures still fail the owner operation rather than reporting success. A 404 can also indicate missing permissions, so check IAM and the configured region if retries are exhausted.

The managed topic is the durable onboarding marker; keep its name/tags intact. An existing topic with a missing subscription is flagged for review, never automatically re-subscribed. This handles unsubscribe decisions conservatively, including ambiguous partial provisioning. After a failed initial subscription creation, inspect the topic and manually add the owner's email only after verifying they have not opted out. Do not delete/recreate managed topics or change the prefix/compartment/region as a routine retry: doing so loses this marker and can trigger new confirmation emails. No persistent publish ledger is provided. A manual rerun can resend already-published reports, and ONS delivery is not guaranteed exactly once.

Owner mode uses `concurrencyPolicy: Forbid`, `restartPolicy: Never`, and `backoffLimit: 0` to avoid automatic whole-job resend after partial failure. It continues other owners and exits nonzero on individual errors. Pending confirmations are normal and do not fail the run. Avoid overlapping manual Jobs. Review Job logs for invalid tags, pending owners, missing subscriptions, quota/rate-limit failures, and publish failures. Check ONS topic quotas before onboarding large numbers of owners.

IAM: retain the existing resource-search, compartment-read, and Usage API permissions. An administrator must additionally authorize topic/subscription administration and publication in the dedicated notification compartment, for example:

```text
Allow dynamic-group <report-dynamic-group> to manage ons-topics in compartment <notification-compartment>
```

Keep managed owner subscriptions in their topic's configured compartment and restrict subscription moves via IAM. Owner mode supplies both compartment and topic IDs when listing subscriptions because the deployed ONS endpoint rejects a null compartment. It must not be relied upon to detect subscribers moved outside that compartment. See [ONS security policies](https://docs.oracle.com/en-us/iaas/Content/Security/Reference/notifications_security.htm) and [email confirmation](https://docs.oracle.com/en-us/iaas/Content/Notification/Tasks/create-subscription-email.htm).

Deployment files: copy the three new modules `owner_routing.py`, `notification_topics.py`, and `expired_resources_owner_notification.py` under `src/modules/reports/`; retain the existing report module. Copy the updated CronJob and ConfigMap templates, and merge the values above. If you use an externally managed ConfigMap, add the `OCI_MGMT_DASH_REPORT_OWNER_*` variables from `sample.env` there yourself. Owner mode uses the SDK region endpoints; the legacy custom `notification.endpoint` applies only to managers mode.

Build/push a new application image tag and set `image.tag` in your deployed values. Then:

```bash
helm upgrade oci-management-portal ./deploy/helm/oci-management-portal \
  --namespace gitdash -f ./deploy/helm/oci-management-portal/my-values.yaml
REPORT_JOB="owner-preview-$(date +%s)"
kubectl create job -n gitdash --from=cronjob/oci-management-portal-expired-report "${REPORT_JOB}"
kubectl logs -n gitdash -f "job/${REPORT_JOB}"
```

With `dryRun: true`, discovery and cost reads run, but no topics, subscriptions or emails are created. Logs include private report content, so restrict access to them. Once reviewed, set `dryRun: false` and upgrade again. Confirm the owners' subscriptions and allow the next run to publish. Switching back to `mode: managers` with the original `notification.topicId` restores shared manager reports; owner topics remain intact. No image rebuild is required just to switch modes after deploying the new image.

```bash
helm upgrade --install oci-management-portal deploy/helm/oci-management-portal \
  --namespace oci-management-portal \
  --create-namespace \
  -f my-values.yaml
```

Check rollout:

```bash
kubectl get pods -n oci-management-portal
kubectl logs -n oci-management-portal deploy/oci-management-portal
```

Run the Helm test:

```bash
helm test oci-management-portal -n oci-management-portal
```
