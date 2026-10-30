# AWS Deployment Architecture and Procedures

This document specifies how the Customer Churn Prediction platform maps to AWS infrastructure for production deployment.

## 1. Architecture Components
*   **Amazon ECS (Elastic Container Service) on Fargate:**
    *   Serverless compute engine for running our Docker containers (`churn-api` and `churn-dashboard`).
    *   Automatically scales based on CPU/Memory thresholds.
*   **Amazon ECR (Elastic Container Registry):**
    *   Hosts our versioned Docker images pushed from GitHub Actions.
*   **Amazon RDS (Relational Database Service):**
    *   Managed PostgreSQL database hosting `prediction_records` and `retention_recommendations`.
    *   Engine version 15 (matches `docker-compose.yml` / CI `postgres:15-alpine`).
    *   Instance class is a **parameter** (`DbInstanceClass`), not hard-coded per environment.
      Staging target: `db.r6g.large` (2 vCPU / 16 GiB, Graviton2). The previous `db.t4g.micro`
      baseline cannot serve this workload: its default `max_connections` (~112) is below the
      application's connection budget (see §6).
    *   Availability is controlled by `DbMultiAZ` alone - the two NAT Gateways do **not** make
      the database highly available.
*   **Amazon S3 (Simple Storage Service):**
    *   Stores the compiled model artifacts (e.g., `model_v1.joblib`). The API container fetches these objects upon startup natively.
*   **Amazon CloudWatch:**
    *   Captures `stdout` JSON logs emitted by our `MetricsMiddleware`.
    *   Configured with Alarms to trigger if `drift_alert` is detected.

## 2. Infrastructure as Code (IaC)
We use AWS CloudFormation to define the ECS Cluster, Task Definitions, and Services in a reproducible manner. (See `cloudformation/ecs-cluster.yml` for the compute template).

## 3. Deployment Verification
After merging to `main` and deploying the newest ECR image:
1.  **Health Check:** Ensure `/health` returns HTTP 200 via the AWS Application Load Balancer (ALB).
2.  **Model Loading:** Query `/model/info` to verify the correct artifact version (`1.0.0`) and Threshold (`0.65`) was loaded successfully from S3 into memory.
3.  **End-to-End Test:** Submit a known `POST /retention-recommendation` payload and confirm the database writes the resultant recommendation record seamlessly.

## 4. Rollback Procedures
If post-deployment checks fail or CloudWatch alerts fire:
1.  **Revert ECS Task Definition:** In the ECS console (or via AWS CLI), update the Service to utilize the previous *stable* revision of the Task Definition.
2.  **Automated Drain:** ECS will spin up the old container version, wait for it to pass health checks, and drain network connections away from the broken deployment.
3.  **Database Consideration:** If Alembic migrations were applied, manual database rollback (`alembic downgrade -1`) must be performed before the ECS rollback completes, ensuring schema compatibility.

## 5. Network Topology (dual NAT Gateway egress)

Both NAT Gateways are created by `cloudformation/ecs-cluster.yml` and are indexed against the
subnet **position** in the parameters, so the caller must supply subnets in the right order:

| Index | Public subnet (parameter) | Private subnet (parameter) | NAT | Private route table |
|---|---|---|---|---|
| 0 | `PublicSubnetIds[0]` (AZ-a) | `PrivateSubnetIds[0]` | `NatGatewayA` (EIP A) | `PrivateRouteTableA` |
| 1 | `PublicSubnetIds[1]` (AZ-b) | `PrivateSubnetIds[1]` | `NatGatewayB` (EIP B) | `PrivateRouteTableB` |

```
Internet ── IGW ── public subnet[AZ-a] ── NatGatewayA ── PrivateRouteTableA ── private subnet[AZ-a] ── ECS tasks
         └─ IGW ── public subnet[AZ-b] ── NatGatewayB ── PrivateRouteTableB ── private subnet[AZ-b] ── ECS tasks
                                                                            └─ ALB (internet-facing, public subnets)
RDS (DatabaseMode=create) lives in the private subnets, SG-restricted to the ECS task SG only.
```

*   Each private subnet routes `0.0.0.0/0` to its **own** NAT Gateway in the matching AZ.
*   The S3 **gateway** endpoint is attached to *both* private route tables (model-artifact reads
    and ECR layer pulls stay on the AWS network). Interface endpoints for `ecr.api`, `ecr.dkr`,
    `logs`, `monitoring` and `secretsmanager` already span both private subnets.
*   ECS tasks keep `AssignPublicIp: DISABLED`; the public path is only the ALB → task SG ingress
    on 8000/8501.
*   Egress from tasks: HTTPS/443 (AWS APIs, external services) and 5432 to the database SG.

**Prerequisites that static validation cannot check** (verify in the account before deploying):
1.  `PublicSubnetIds[0]` and `PrivateSubnetIds[0]` are in the same AZ, `[1]` in a second AZ.
2.  Both public subnets have a route to an Internet Gateway - a NAT Gateway in a non-IGW-routed
    subnet fails to become available.
3.  `PrivateSubnetIds` are in at least two AZs (required by the RDS DB subnet group / Multi-AZ).
4.  Route tables of the private subnets are not otherwise pre-associated by another stack; this
    stack **replaces** those associations.

**What two NAT Gateways protect against:** loss of the single AZ hosting the only NAT (e.g. AZ
outage, NAT host impairment, exhausted single-NAT bandwidth/ports) no longer cuts off egress for
*both* private subnets; each AZ keeps its own outbound path, so tasks in the surviving AZ can
still pull from ECR, reach Secrets Manager/CloudWatch through their endpoints, and call external
APIs.

**What they do NOT protect against:**
*   **Database availability** - nothing in the NAT layer affects RDS. Database HA is `DbMultiAZ` only.
*   Cross-AZ task placement during a full-region failure, or ALB/certificate/ECR outage.
*   Data-plane durability (S3/Route53 are already multi-AZ).
*   Cost-efficient egress: NAT processing ($0.045/GB) still applies in both AZs; only cross-AZ
    "hairpinning" through a single NAT is avoided.

## 6. RDS Configuration, Capacity and Multi-AZ Decision

### 6.1 Database mode
`DatabaseMode` (new parameter) selects one of two mutually exclusive paths:

| Mode | Meaning | Resources created |
|---|---|---|
| `external` (default) | Existing, externally managed RDS. `DatabaseEndpoint` (hostname only) + `DatabaseSecretArn` are **required** and enforced by the template `Rules` section. | none |
| `create` | Stack provisions RDS for PostgreSQL in the private subnets. | `DatabaseSecret`, `DatabaseSubnetGroup`, `DatabaseInstance`, `DatabaseSecretAttachment` |

Capacity parameters (only meaningful for `create`, so they are not hard-coded into the resource):

| Parameter | Default | Notes |
|---|---|---|
| `DbInstanceClass` | `db.r6g.large` | 2 vCPU / 16 GiB, Graviton2. `db.r6g.large` supports PostgreSQL 12-18 and is listed for us-east-1; **verify class availability in the actual target region and the account's RDS quotas before deploying elsewhere**. |
| `DbEngineVersion` | `15` | Matches local/CI `postgres:15-alpine`. |
| `DbMultiAZ` | `true` | See §6.3. |
| `DbAllocatedStorage` | `20` GiB (gp3) | Minimum for gp3. |
| `DbBackupRetentionDays` | `7` | `0` disables automated backups (staging only). |

Other settings: `StorageEncrypted: true` (AWS-managed `aws/rds` key), `PubliclyAccessible: false`,
`DeletionPolicy/UpdateReplacePolicy: Snapshot`, port from `DatabasePort` (5432), credentials
generated into `DatabaseSecret` (32 chars) and referenced through CloudFormation dynamic
references; security group is the existing `DatabaseSecurityGroup` (ingress 5432 from the ECS task
SG only).

### 6.2 Connection budget (from the actual configuration)

Formula: `maximum workers × (pool_size + max_overflow) × maximum replicas`

| Component | Value | Source |
|---|---|---|
| Workers per API task | 2 | `ApiTaskDefinition` `Command: --workers 2` (explicit; see §7) |
| `pool_size` | 5 | `src/config.py` `DB_POOL_SIZE` default |
| `max_overflow` | 10 | `src/config.py` `DB_MAX_OVERFLOW` default |
| Connections per task | 2 × (5 + 10) = **30** | |
| API tasks at `DesiredApiCount` default | 2 → **60** | `DesiredApiCount` |
| API tasks at auto-scaling max | 10 → **300** | `ApiScalingTarget.MaxCapacity` |
| Migration job (`RunMigrations=true`) | **+2** | one `alembic upgrade head` task (1 conn + margin) |
| Ops/monitoring/psql | **+1** | manual sessions |
| **Worst-case total** | **303** | |

Capacity check for `db.r6g.large` (us-east-1, PostgreSQL 15):

*   RDS default parameter group formula (AWS docs, *Quotas and constraints for Amazon RDS*):
    `max_connections = LEAST({DBInstanceClassMemory} / 9531392, 5000)`
*   `db.r6g.large` = 16 GiB = 17,179,869,184 B → 17,179,869,184 / 9,531,392 = **1,802**
    (≈1,800 after instance-reserved memory is excluded).
*   303 required vs **≈1,800 available → 17% of budget, sufficient with large headroom**
    (2× safety factor vs the old `db.t4g.micro` baseline, whose 1 GiB gives
    1,073,741,824 / 9,531,392 = **112** connections - *insufficient*, and 1 GiB RAM would not
    have carried the pool either).
*   Memory: `shared_buffers` defaults to 25% of instance memory (≈4 GiB) plus ≈2-3 GiB for 303
    backends at ~9 MiB each → ≈7-8 GiB of 16 GiB. **Estimate only - confirm with
    `SHOW max_connections;` and CloudWatch `DatabaseConnections`/`FreeableMemory` in staging.**
*   Headroom rule to re-check whenever sizing changes:
    `workers × (pool_size + max_overflow) × max_tasks × 1.1 ≤ max_connections`
    → 300 × 1.1 = 330 ≤ 1,800 ✓. Raising `DesiredApiCount`/`MaxCapacity` or pool sizes
    invalidates this calculation.

### 6.3 Multi-AZ decision (independent of NAT)
**Decision: `DbMultiAZ=true` by default for staging**, because staging exists to verify database
failover; `DatabaseInstance.MultiAZ: !If [DatabaseMultiAzEnabled, true, false]` makes the setting
explicit and parameter-driven.

*   `DbMultiAZ=true` → Multi-AZ: synchronous standby in a second AZ, automatic failover in
    typically < 60 s. This is the only way this stack provides a *highly available* database.
*   `DbMultiAZ=false` → **intentionally single-AZ** to cut staging cost. It is then correct to
    describe it as *"a single-AZ database with no automatic failover"*, not as highly available.
    A full AZ failure then means downtime until manual restore from snapshot/backup (RPO up to
    `DbBackupRetentionDays`, typically minutes with transactional backups, worst case up to the
    backup window).
*   Two NAT Gateways, an ALB in two AZs and ECS tasks across two AZs give **no** database
    failover. Do not conflate them.

Failover verification procedure (staging, after authorized deployment): trigger a Reboot-with-failover
(`aws rds reboot-db-instance --db-instance-identifier churn-db-staging --force-failover`), then confirm
`/ready` recovers, connections re-establish (`pool_pre_ping` is on), and the ALB target stays healthy.

## 7. Cost Assumptions (us-east-1 list prices, October 2026, 720 h/month, on-demand)

| Item | Unit price | Monthly (staging) | Delta vs. previous single-NAT/no-DB design |
|---|---|---|---|
| NAT Gateway (existing) | $0.045/h + $0.045/GB processed | $32.40 | - |
| **Second NAT Gateway (new)** | $0.045/h + $0.045/GB processed | **+$32.40** | **+$32.40** |
| RDS `db.r6g.large` Single-AZ | $0.225/h | ≈$164.30 (incl. 20 GiB gp3 @ $0.115 = $2.30) | new if `DatabaseMode=create` |
| RDS `db.r6g.large` Multi-AZ | ≈2× compute (billed standby) + 2× storage ($0.23/GB-mo) | ≈**$328.60** ($324.00 + $4.60) | **+$164.30 vs Single-AZ** |

*   Automated-backup storage up to the provisioned storage size is not charged separately;
    backup storage beyond that is billed per GB-month (region-dependent, ≈$0.095/GB-month) -
    confirm on the RDS pricing page at deploy time.
*   Interface VPC endpoints (~$0.01/h per AZ per endpoint, 5 interfaces here) already exist in the
    template; they are unchanged by this work but are part of the same bill.
*   Prices move; treat every figure as an estimate to re-confirm, not a quote. Free-tier/credits
    do not apply to `db.r6g.*`.

**Total incremental cost of the availability work: ≈+$32.40/month (second NAT) plus, if Multi-AZ
is kept in staging, ≈+$164.30/month → ≈+$196.70/month.** Set `DbMultiAZ=false` for a cheap
throwaway staging stack, accepting single-AZ explicitly.

## 8. Prerequisites Checklist for an Authorized Staging Deployment

Required parameter values (no defaults, or enforced by `Rules`):

| Parameter | Requirement |
|---|---|
| `VpcId` | Existing VPC with ≥2 private + ≥2 public subnets in ≥2 AZs |
| `PrivateSubnetIds` / `PublicSubnetIds` | **Ordered AZ pairs** (index 0 = AZ-a, index 1 = AZ-b); public subnets routed to an IGW |
| `ApiImageUrl` / `DashboardImageUrl` | ECR image URIs in the target account/region |
| `SSLCertificateArn` | ACM cert in the same region, covering the ALB DNS name |
| `ApiKeySecretArn` | Secrets Manager ARN with JSON key `key` (≥32 chars) |
| `DatabaseMode=external` | `DatabaseEndpoint` (hostname only) **and** `DatabaseSecretArn` (keys `username`,`password`) - enforced by `Rules` |
| `DatabaseMode=create` | `DbInstanceClass`, `DbEngineVersion`, `DbMultiAZ`, `DbAllocatedStorage`, `DbBackupRetentionDays` |
| `Environment` | `staging` (no ALB access-log bucket, ALB deletion protection off) / `production` (access-log bucket + deletion protection on) |

Also required outside the template: AWS credentials with permission to create ECS/EC2/ELB/RDS/
IAM/Secrets Manager/S3/KMS/CloudWatch resources, and the ECR images already pushed.

## 9. Validation Performed and Current Status

| Check | Command | Result |
|---|---|---|
| Template lint | `cfn-lint cloudformation/ecs-cluster.yml` | **0 errors, 0 warnings** (`cfn-lint 1.57.2`; config in `.cfnlintrc.yaml` documents the single suppressed rule `W1030` and why) |
| Invalid `GetAtt` fixed | `!GetAtt ApiService.ServiceName` → `!GetAtt ApiService.Name` (4 alarms) | `AWS::ECS::Service` exposes only `Name`/`ServiceArn`; the previous value was hidden by a `cfn-lint` `E1010` suppression and **would have failed stack creation** |
| `aws cloudformation validate-template` | not available | **BLOCKED** - no AWS CLI or credentials in this environment |
| Staging deployment / runtime behaviour | - | **BLOCKED** - not attempted; no deployment evidence exists, and none is claimed |

Static lint does not substitute for a deployment test. The first authorized staging deploy must
verify, at minimum: NAT availability in both AZs, image pull from a private subnet, ALB health
checks returning 200 (rate-limit note in §10), model artifact load from S3, RDS connectivity from
all task ENIs, `SHOW max_connections;` ≈1,800, and Multi-AZ failover behaviour.

## 10. Known Findings Not Changed by This Work

1.  **Task egress is not yet least-privilege.** `ECSTaskSecurityGroup` declares no inline
    `SecurityGroupEgress`, so CloudFormation creates the default allow-all egress rule and the
    explicit 443/5432 rules are additive. Verify after deploy with
    `aws ec2 describe-security-groups`; tightening it (e.g. to 443/53/5432) requires runtime
    verification of DNS and task-metadata reachability first.
2.  **Secrets are embedded in the task definition.** `{{resolve:secretsmanager:...}}` in container
    `Environment` is resolved by CloudFormation at create time, so credentials are readable by
    anyone with `ecs:DescribeTaskDefinition`. Recommended follow-up: move to the ECS `secrets`
    section, which requires splitting `DATABASE_URL` into components the app can assemble.
3.  **`MigrationService` is a long-running ECS service, not a one-shot job.** After `alembic
    upgrade head` exits, ECS starts another task (idempotent no-op), and when
    `RunMigrations=true` it can race API-service rollout (CloudFormation does not order them,
    and `DependsOn` cannot reference a conditional resource). Recommended: run migrations as a
    separate, ordered deployment step (or `aws ecs run-task --wait`) before rolling the API.
4.  **Bucket deletion blocks stack teardown.** `AlbAccessLogsBucket` (production) and
    `ModelArtifactsBucket` hold objects, so `DeleteStack` fails until they are emptied. Only ALB
    deletion protection was made environment-conditional.
5.  **`/health` is rate-limited** (`RATE_LIMIT_DEFAULT=100/minute`, keyed by API key prefix or
    client IP). ALB health checks share one ALB-node IP bucket; watch for 429s under anonymous
    load, since the target-group matcher accepts only 200.
6.  **`Dockerfile.api` CMD cannot work as written**: it embeds `${VAR:-default}` in a JSON
    exec-form array, which no shell expands. The task definition now sets `EntryPoint` + `Command`
    explicitly (`--workers 2`, keep-alive 75 s), which is also what the connection budget in §6.2
    depends on. Fixing the Dockerfile remains an application-side task.
7.  **RDS engine log export is not enabled** (it would create `/aws/rds/instance/...` log groups;
    retention must be pre-set to avoid unbounded logs). Enable and verify in staging if DB engine
    logs are required.
