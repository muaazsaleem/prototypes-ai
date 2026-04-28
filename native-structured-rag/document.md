# Zephyr Cloud Storage API — Product Specification v2.1

**Document Status:** Final  
**Last Updated:** March 2025  
**Owner:** Platform Engineering  

---

## 1. Overview

Zephyr Cloud Storage is a distributed object storage platform designed for high-throughput workloads, developer-first integrations, and enterprise-grade reliability. This specification covers API behavior, constraints, rate limits, security requirements, and SLA commitments for Zephyr Storage v2.x.

Zephyr Storage is organized around the concept of **buckets** and **objects**. A bucket is a top-level namespace uniquely identified by a globally unique name. Objects are stored within buckets and are individually addressable via a key. Each object can carry up to 10 KB of user-defined metadata.

The API is REST-based, using JSON payloads for control-plane operations and raw binary streams for data-plane operations. All requests must be made over HTTPS. HTTP connections are rejected at the load balancer with a 301 redirect.

Versioning is handled through the `X-Zephyr-API-Version` request header. Omitting the header defaults to the latest stable version. Clients should pin to a specific version in production to avoid unexpected behavior changes.

### 1.1 Intended Audience

This document targets backend engineers integrating Zephyr into their applications, DevOps teams managing infrastructure, and security engineers evaluating compliance requirements. It assumes familiarity with REST APIs, HTTP/2, and cloud object storage concepts.

### 1.2 Key Capabilities

- Multi-region replication with configurable consistency guarantees
- Byte-range downloads and resumable uploads
- Presigned URLs for temporary, credential-free access
- Event-driven architecture via webhooks
- Fine-grained IAM with bucket-level and prefix-level policies
- Native support for immutable (WORM) storage
- Lifecycle policies for automated tiering and deletion

---

## 2. Authentication and Authorization

Zephyr supports three authentication mechanisms, each suited to different deployment scenarios. All mechanisms produce a short-lived access token that is validated on every request.

### 2.1 API Key Authentication

API keys are long-lived credentials tied to a service account. They are the recommended authentication method for server-to-server integrations. An API key is passed in the `Authorization` header using the `Bearer` scheme:

```
Authorization: Bearer zsk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Keys are prefixed with `zsk_live_` for production and `zsk_test_` for sandbox environments. Keys do not expire automatically but can be rotated manually from the dashboard. Each service account can have a maximum of 10 active API keys at any time.

Leaked keys can be revoked immediately from the dashboard. Revocation takes effect within 60 seconds across all edge nodes globally.

### 2.2 OAuth 2.0

For user-facing applications where access is delegated on behalf of an end user, Zephyr supports the OAuth 2.0 Authorization Code Flow with PKCE. Scopes are defined at the bucket level. The token endpoint is:

```
POST https://auth.zephyrstorage.io/oauth/token
```

Access tokens have a TTL of 3,600 seconds (1 hour). Refresh tokens are valid for 30 days and can be used to obtain new access tokens without requiring the user to re-authenticate. Refresh token rotation is enabled by default: each use of a refresh token invalidates the previous one and issues a new one.

### 2.3 Enterprise SSO

Enterprise customers on the Business or Enterprise tier can configure SAML 2.0-based Single Sign-On. SAML 2.0 is the required authentication method for Enterprise SSO integration. The identity provider (IdP) must support SAML 2.0 and provide a valid metadata XML endpoint. Supported IdPs include Okta, Azure Active Directory, Google Workspace, and Ping Identity.

Upon successful SSO login, Zephyr issues a session token valid for 8 hours. Session tokens are bound to the originating IP address by default; this restriction can be disabled for mobile or VPN scenarios from the Enterprise settings panel.

Role mapping is performed by matching IdP group names to Zephyr roles. The default roles are `viewer`, `editor`, and `admin`. Custom roles can be defined with granular permission sets.

---

## 3. File Upload API

Zephyr provides two upload paths: a single-request upload for small files and a multipart upload for large files. Clients should select the appropriate path based on file size.

### 3.1 Single File Upload

A single-request upload sends the entire object in one HTTP PUT request:

```
PUT /v2/buckets/{bucket}/objects/{key}
Host: api.zephyrstorage.io
Content-Type: application/octet-stream
Content-Length: <bytes>

<binary data>
```

The server responds with `201 Created` on success, including the object's ETag (MD5 of the content) and the canonical object URL. If an object with the same key already exists, it is overwritten unless bucket versioning is enabled.

### 3.2 Multipart Upload

For objects larger than 100 MB, multipart upload is strongly recommended. Multipart upload provides resilience: if a part upload fails, only that part needs to be retried. The workflow is:

1. **Initiate**: `POST /v2/buckets/{bucket}/objects/{key}/multipart` returns an `upload_id`.
2. **Upload parts**: `PUT /v2/buckets/{bucket}/objects/{key}/multipart/{upload_id}/parts/{part_number}`. Each part must be at least 5 MB, except the last part. Part numbers range from 1 to 10,000.
3. **Complete**: `POST /v2/buckets/{bucket}/objects/{key}/multipart/{upload_id}/complete` with a JSON array of `{part_number, etag}` pairs.
4. **Abort** (optional): `DELETE /v2/buckets/{bucket}/objects/{key}/multipart/{upload_id}` to clean up incomplete uploads.

Incomplete multipart uploads incur storage charges and should be cleaned up using lifecycle rules or explicit abort calls.

### 3.3 Upload Constraints

The following constraints apply to all upload operations:

| Constraint | Single Upload | Multipart Upload |
|---|---|---|
| Maximum file size | **5 GB** | 5 TB |
| Minimum part size | N/A | 5 MB |
| Maximum part size | N/A | 5 GB |
| Maximum parts per upload | N/A | 10,000 |
| Maximum concurrent uploads per key | 1 | 1 |
| Request timeout | 30 seconds | 120 seconds per part |

Objects exceeding 5 GB must use the multipart upload API. Attempts to upload a file larger than 5 GB via the single-request upload path return `413 Content Too Large`. The overall maximum object size is 5 TB, achievable only through multipart upload.

---

## 4. File Download and Retrieval

### 4.1 Direct Download

Objects are downloaded via a GET request:

```
GET /v2/buckets/{bucket}/objects/{key}
```

Responses include `Content-Type`, `Content-Length`, `ETag`, and `Last-Modified` headers. Conditional requests using `If-None-Match` and `If-Modified-Since` are supported, returning `304 Not Modified` when the object has not changed.

Byte-range downloads are supported using the `Range` header:

```
Range: bytes=0-1048575
```

This retrieves the first 1 MB. Partial responses return HTTP 206. Range requests are useful for streaming media, progressive file access, and resuming interrupted downloads.

### 4.2 Presigned URLs

Presigned URLs allow time-limited, credential-free access to objects. They are generated server-side and can be shared externally. To generate a presigned URL:

```
POST /v2/buckets/{bucket}/objects/{key}/presign
{
  "expires_in": 3600,
  "method": "GET"
}
```

The response contains a `url` field valid for the specified duration (maximum 7 days). Presigned URLs encode the signature in the query string, not headers, making them usable in standard browser `<img>` and `<a>` tags.

Presigned PUT URLs can be generated to allow direct browser-to-storage uploads without routing through the application server.

### 4.3 CDN Integration

Zephyr integrates natively with CloudFront, Fastly, and Cloudflare. When CDN integration is enabled for a bucket, all GET requests are automatically served through the configured CDN edge network. Cache-Control headers returned by Zephyr are respected by CDN nodes. Custom origin headers can be set per-bucket to prevent CDN bypass.

---

## 5. File Management

### 5.1 Listing Objects

Objects within a bucket can be listed using the list endpoint:

```
GET /v2/buckets/{bucket}/objects?prefix={prefix}&limit={n}&cursor={cursor}
```

Results are returned in lexicographic order by key. Pagination is cursor-based; each response includes a `next_cursor` field. A `delimiter` parameter enables pseudo-directory listings by treating the delimiter character as a folder separator.

### 5.2 Moving and Copying

Objects can be copied within and across buckets:

```
POST /v2/buckets/{bucket}/objects/{key}/copy
{
  "destination_bucket": "target-bucket",
  "destination_key": "new-key"
}
```

Copy operations are server-side and do not consume client bandwidth. Cross-region copies incur a small latency overhead (typically under 500 ms). Server-side copies are atomic; the destination object is not visible until the copy completes.

Rename operations are implemented as copy-then-delete. There is no atomic rename primitive in the API.

### 5.3 Deletion and Soft Delete

Objects are deleted via:

```
DELETE /v2/buckets/{bucket}/objects/{key}
```

When bucket versioning is enabled, a delete marker is created instead of permanently removing the object. When versioning is disabled, the object moves to the soft-delete state.

---

## 6. Rate Limiting and Quotas

### 6.1 Request Rate Limits

Rate limits are enforced per API key (or per session token for OAuth) at the edge, before requests reach the storage backend. Limits are applied on a sliding-window basis over a 60-second window.

| Tier | Requests per Minute | Burst Allowance |
|---|---|---|
| Free | 100 | 120 for up to 5 seconds |
| Starter | 1,000 | 1,200 for up to 10 seconds |
| Business | 10,000 | 12,000 for up to 15 seconds |
| Enterprise | Custom (default 100,000) | Negotiated |

The Free tier allows **100 requests per minute** as the baseline rate limit. Requests exceeding the limit receive `429 Too Many Requests` with a `Retry-After` header indicating the number of seconds until the window resets. The `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers are included on every response.

### 6.2 Bandwidth Quotas

Egress bandwidth is metered separately from request count. Monthly egress quotas:

| Tier | Monthly Egress | Overage Rate |
|---|---|---|
| Free | 10 GB | Not available (hard cap) |
| Starter | 100 GB | $0.08/GB |
| Business | 1 TB | $0.06/GB |
| Enterprise | Custom | Negotiated |

Ingress (upload) bandwidth is not metered or charged.

### 6.3 Storage Quotas

| Tier | Max Storage | Max Objects per Bucket |
|---|---|---|
| Free | 5 GB | 100,000 |
| Starter | 500 GB | 10,000,000 |
| Business | Unlimited | Unlimited |
| Enterprise | Unlimited | Unlimited |

Storage quotas are enforced at the account level, not the bucket level. Free tier accounts that exceed 5 GB will have uploads blocked until storage is freed.

---

## 7. Error Handling

### 7.1 Error Response Format

All errors are returned as JSON:

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Request rate limit of 100/min exceeded.",
    "request_id": "req_01HQVP8K3M7J9XNCZ4W6YR2D5B",
    "retry_after": 14
  }
}
```

The `request_id` field is unique per request and should be included in support tickets.

### 7.2 Retry Strategy

Clients should implement exponential backoff with jitter for all 5xx errors and `429 Too Many Requests`. Recommended initial delay: 500 ms. Maximum delay: 32 seconds. Maximum retry attempts: 5.

Do not retry 4xx errors except `408 Request Timeout` and `429 Too Many Requests`.

### 7.3 Common Error Codes

| Code | HTTP Status | Description |
|---|---|---|
| `OBJECT_NOT_FOUND` | 404 | Object key does not exist in bucket |
| `BUCKET_NOT_FOUND` | 404 | Bucket does not exist or access denied |
| `ACCESS_DENIED` | 403 | Insufficient permissions for operation |
| `RATE_LIMIT_EXCEEDED` | 429 | Per-key rate limit exceeded |
| `QUOTA_EXCEEDED` | 429 | Storage or bandwidth quota reached |
| `OBJECT_TOO_LARGE` | 413 | File exceeds 5 GB single-upload limit |
| `CHECKSUM_MISMATCH` | 400 | Uploaded data does not match provided checksum |
| `BUCKET_ALREADY_EXISTS` | 409 | Bucket name already taken globally |
| `INVALID_KEY` | 400 | Object key contains invalid characters |

---

## 8. Data Retention and Lifecycle

### 8.1 Active File Retention

Active (non-deleted) objects are retained indefinitely as long as the account remains active and in good standing. There is no maximum age for active objects. Zephyr does not perform any automatic deletion of active objects unless a lifecycle rule is configured by the account holder.

### 8.2 Deleted File Recovery Window

When an object is deleted (and bucket versioning is disabled), it enters a soft-delete state. Deleted files are retained for **30 days** before permanent, irreversible deletion. During this 30-day recovery window, objects can be restored via the API:

```
POST /v2/buckets/{bucket}/objects/{key}/restore
```

The restore operation moves the object back to the active state with its original metadata intact. After the 30-day window expires, the object is permanently purged from all storage nodes and cannot be recovered.

For accounts on the Business or Enterprise tier, the deleted file retention window can be extended up to 90 days from the account settings panel.

### 8.3 Lifecycle Policies

Lifecycle policies automate object management based on age, prefix, or storage class. Supported actions:

- **Transition**: Move objects to a cheaper storage class (e.g., Standard → Archive) after a specified number of days.
- **Expire**: Permanently delete objects after a specified number of days from creation.
- **Abort Multipart**: Automatically abort incomplete multipart uploads older than a specified number of days.

Lifecycle rules are evaluated daily at 02:00 UTC. Objects matching a rule are acted on within 24 hours of the evaluation window.

---

## 9. Security and Compliance

### 9.1 Encryption at Rest

All objects stored in Zephyr are encrypted at rest using AES-256-GCM. Encryption is performed transparently at the storage layer; no client-side action is required. Each object is encrypted with a unique data encryption key (DEK), and the DEK is itself encrypted by a key encryption key (KEK) managed in Zephyr's hardware security module (HSM) fleet.

Customers on the Business and Enterprise tiers can enable **Customer-Managed Keys (CMK)** using keys stored in AWS KMS, Google Cloud KMS, or Azure Key Vault. With CMK enabled, Zephyr cannot access object data if the customer's key is disabled or deleted.

### 9.2 Encryption in Transit

All API traffic uses TLS 1.2 or higher. TLS 1.0 and TLS 1.1 are not supported and connections using these versions are rejected. Zephyr enforces HTTP Strict Transport Security (HSTS) with a max-age of 31,536,000 seconds on all endpoints.

Certificate pinning is supported for mobile SDKs and is recommended for high-security applications.

### 9.3 Compliance Certifications

Zephyr holds the following security and compliance certifications as of the latest document revision date. These certifications are independently audited:

- SOC 2 Type II (renewed annually)
- ISO 27001
- PCI-DSS Level 1 (for payment-adjacent workloads)
- HIPAA Business Associate Agreement (BAA) available on Enterprise tier
- GDPR data processing addendum (DPA) available for all paying tiers
- CCPA compliance framework (available for US customers)
- FedRAMP Moderate (currently In Process, ETA Q4)

All compliance reports are available to paying customers through the Trust Center dashboard.

### 9.4 Access Audit Logs

Every API request is recorded in the audit log, including the caller identity, IP address, request timestamp, HTTP method, resource accessed, and response status code. Audit logs are retained for 12 months on the Business tier and 7 years on the Enterprise tier.

Audit logs can be streamed in real time to an S3-compatible endpoint, Splunk, or Datadog using the Log Streaming feature.

---

## 10. SLA and Performance Guarantees

### 10.1 Uptime SLA

Zephyr commits to the following monthly uptime SLAs:

| Tier | Monthly Uptime SLA | Compensation (if breached) |
|---|---|---|
| Free | No SLA | None |
| Starter | 99.9% | Service credit: 10% of monthly spend |
| Business | 99.95% | Service credit: 15% of monthly spend |
| Enterprise | 99.99% | Service credit: 25% of monthly spend |

The paid tier uptime SLA is **99.95%** for the Business tier, rising to 99.99% for Enterprise. "Uptime" is defined as the API being able to successfully process valid requests, measured from Zephyr's external monitoring endpoints. Scheduled maintenance windows (announced 72 hours in advance) are excluded from uptime calculations.

### 10.2 Latency SLA

For single-region requests within the same geographic region as the storage bucket. The values below represent internal processing time and are critical for understanding the performance profile of the Zephyr storage engine under varying load conditions.

| Percentile | Read Operations | Write Operations |
|---|---|---|
| p50 Target | 15 ms | 25 ms |
| p75 Target | 20 ms | 35 ms |
| p80 Target | 25 ms | 45 ms |
| p90 Target | 35 ms | 55 ms |
| p95 Target | 50 ms | 85 ms |
| p99 Target | 75 ms | 120 ms |
| p99.9 Target | 150 ms | 250 ms |

These figures represent the Zephyr API server's processing time and exclude client-side network latency.

### 10.3 Incident Response

All incidents affecting service availability or data durability are published to the public status page at `status.zephyrstorage.io`. Incident categories:

- **P1 (Critical)**: Data loss, complete API unavailability. Response time: 15 minutes.
- **P2 (High)**: Significant degradation in availability or performance. Response time: 30 minutes.
- **P3 (Medium)**: Minor performance degradation or non-critical feature outage. Response time: 2 hours.

Enterprise customers receive direct incident notifications via PagerDuty integration or dedicated Slack channel.

---

## 11. Pricing and Billing

### 11.1 Storage Pricing

Storage is billed per GB-month, prorated to the hour. The effective price depends on the storage class:

| Storage Class | Price per GB-Month |
|---|---|
| Standard | $0.023 |
| Infrequent Access | $0.012 |
| Archive | $0.004 |
| Deep Archive | $0.001 |

Free tier accounts receive 5 GB of Standard storage at no charge.

### 11.2 API Call Pricing

The following API call pricing applies to all regions and is metered independently of bandwidth and storage quotas. Pricing is calculated per thousand requests.

| Operation | Paid Tiers (Starter/Business/Enterprise) | Free Tier |
|---|---|---|
| PUT | $0.005 per 1,000 requests | Free |
| POST | $0.005 per 1,000 requests | Free |
| COPY | $0.005 per 1,000 requests | Free |
| GET | $0.0004 per 1,000 requests | Free up to 50,000/month |
| HEAD | $0.0004 per 1,000 requests | Free up to 50,000/month |
| LIST | $0.0004 per 1,000 requests | Free up to 50,000/month |
| DELETE | Free | Free |
| RESTORE | Free | Not applicable |

### 11.3 Egress Pricing

Internet egress (data transfer out to the public internet) is charged at the rates listed in section 6.2. Data transfer between Zephyr regions and to Zephyr's partner CDN providers is free.

### 11.4 Enterprise Tier

Enterprise tier pricing is custom and negotiated based on expected storage volume, API call volume, egress requirements, and SLA needs. Enterprise contracts include a minimum annual commitment. Custom pricing is available for storage volumes above 1 PB per month.

---

## 12. Webhooks and Event Notifications

### 12.1 Event Types

Zephyr emits events for the following object lifecycle actions:

| Event | Triggered When |
|---|---|
| `object.created` | Object successfully uploaded |
| `object.deleted` | Object deleted (soft or hard) |
| `object.restored` | Soft-deleted object restored |
| `object.tiered` | Object transitioned to a new storage class |
| `bucket.created` | New bucket created |
| `bucket.deleted` | Bucket deleted |

### 12.2 Webhook Configuration

Webhooks are configured per bucket with a target HTTPS endpoint:

```json
{
  "url": "https://your-app.example.com/hooks/zephyr",
  "events": ["object.created", "object.deleted"],
  "secret": "whsec_xxxxxxxxxxxxxxxx"
}
```

Zephyr signs all webhook payloads using HMAC-SHA256 with the configured secret. Consumers must verify the `X-Zephyr-Signature` header before processing events.

### 12.3 Delivery Guarantees

Webhooks are delivered with **at-least-once** semantics. Consumers must be idempotent. Zephyr retries delivery up to 3 times with exponential backoff if the endpoint returns a non-2xx response or times out.

---

## 13. SDK and Client Libraries

### 13.1 Official SDKs

Zephyr provides officially supported SDKs for the following languages, distributed via their respective package managers.

| Language | Package Name | Min Language Version |
|---|---|---|
| Python | `zephyr-storage-python` | Python 3.8+ |
| Node.js | `@zephyr/storage-sdk` | Node 18+ |
| Go | `github.com/zephyrstorage/sdk-go` | Go 1.21+ |
| Java | `io.zephyrstorage:sdk-java` | Java 11+ |
| Ruby | `zephyr_storage` | Ruby 3.0+ |
| Rust | `zephyr-rs` | Rust 1.70+ |
| PHP | `zephyr/storage` | PHP 8.1+ |
| .NET | `Zephyr.Storage` | .NET 6.0+ |

Community SDKs exist for other languages but are not officially supported.

### 13.2 SDK Code Example

```python
from zephyr_storage import ZephyrClient

client = ZephyrClient(api_key="zsk_live_...")

# Upload a file
with open("report.pdf", "rb") as f:
    client.buckets("my-bucket").objects.put("reports/q4.pdf", f)

# Generate presigned URL
url = client.buckets("my-bucket").objects.presign("reports/q4.pdf", expires_in=3600)
```

---

## 14. Versioning and Deprecation Policy

### 14.1 API Versioning

Zephyr uses date-based API versions in the format `YYYY-MM-DD`. The current stable version is `2025-03-01`. Clients specify the version via the `X-Zephyr-API-Version` header. Omitting the header routes to the latest stable version.

Breaking changes are never introduced in a minor update. A new API version is released for any breaking change.

### 14.2 Deprecation Timeline

When an API version is deprecated:

1. Deprecation is announced with at least 12 months notice.
2. The deprecated version continues to work for 12 months from the deprecation announcement.
3. After 12 months, the deprecated version returns `410 Gone` for all requests.

Deprecation notices are communicated via the developer newsletter, the changelog at `docs.zephyrstorage.io/changelog`, and the API response header `X-Zephyr-Deprecation-Warning`.

---

## 15. Support and Escalation

### 15.1 Support Tiers

| Tier | Channel | Initial Response Time |
|---|---|---|
| Free | Community forum only | Best effort |
| Starter | Email | 2 business days |
| Business | Email + chat | 8 business hours |
| Enterprise | Email + chat + phone | 1 business hour |

### 15.2 Scope of Support

Zephyr Support covers API behavior, account configuration, billing issues, and integration troubleshooting. Application-level debugging (e.g., reviewing customer code, architecture reviews) is available as a paid Professional Services engagement.

---

## Appendix A: Glossary

**Bucket**: A top-level namespace for storing objects. Globally unique.  
**Object**: A discrete file stored in a bucket, identified by a key.  
**Key**: The string identifier for an object within a bucket. May include `/` characters to simulate directory structure.  
**ETag**: An MD5 hash of the object content, used for integrity verification and conditional requests.  
**Presigned URL**: A time-limited, credential-embedded URL granting temporary access to a specific object.  
**Soft Delete**: A reversible deletion that retains the object for 30 days before permanent removal.  
**Multipart Upload**: A protocol for uploading large objects in independently resumable parts.  
**DEK/KEK**: Data Encryption Key and Key Encryption Key, used in Zephyr's envelope encryption model.  

---

## 17. Deprecated Endpoints

The following endpoints are scheduled for removal in v3.0 and should not be used in new applications. They currently return a `X-Zephyr-Deprecation-Warning` header.

- `GET /v1/buckets/{bucket}/stats` (Use `/v2/buckets/{bucket}/metrics` instead)
- `POST /v1/buckets/{bucket}/objects/{key}/acl` (Use IAM policies instead)
- `PUT /v1/buckets/{bucket}/cors` (CORS is now managed via the developer dashboard)
- `GET /v1/users/me/keys` (Use the new `/v2/iam/service-accounts/keys` endpoint)
- `DELETE /v1/objects/bulk` (Use the lifecycle policy API for bulk deletions)
- `POST /v1/events/subscribe` (Webhooks now use the `/v2/buckets/{bucket}/webhooks` endpoint)
- `GET /v1/billing/usage` (Moved to the billing portal API)
- `PUT /v1/objects/{key}/metadata` (Metadata is now immutable after object creation)

---

## Appendix B: HTTP Status Code Summary

The following HTTP status codes are returned by the Zephyr API. Any code not on this list should be treated as a generic 500.

| Status | Meaning in Zephyr Context |
|---|---|
| 200 OK | Successful GET or HEAD |
| 201 Created | Successful PUT or multipart complete |
| 204 No Content | Successful DELETE |
| 206 Partial Content | Successful byte-range GET |
| 301 Moved Permanently | HTTP request redirected to HTTPS |
| 304 Not Modified | Conditional GET; object unchanged |
| 400 Bad Request | Malformed request, invalid parameters |
| 401 Unauthorized | Missing or invalid credentials |
| 403 Forbidden | Valid credentials but insufficient permissions |
| 404 Not Found | Object or bucket does not exist |
| 408 Request Timeout | Upload timed out |
| 409 Conflict | Bucket name already taken |
| 410 Gone | Deprecated API version accessed |
| 413 Content Too Large | Upload exceeds 5 GB single-upload limit |
| 429 Too Many Requests | Rate limit or quota exceeded |
| 500 Internal Server Error | Unexpected server error; retry with backoff |
| 503 Service Unavailable | Temporary outage; retry with backoff |


