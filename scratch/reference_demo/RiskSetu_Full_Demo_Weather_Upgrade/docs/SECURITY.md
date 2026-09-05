# Security and deployment boundaries

Implemented: API authentication, current database-based officer approval, admin-only approval, client-field rejection, input bounds, per-IP write/login limiting, private media, image validation/re-encoding, 5 MB upload cap, report idempotency, one confirmation per account/incident, nearby-distance checks, immutable audit entries through the application, explicit CORS origins, service-only database writes and RLS read policies.

Demo mode uses SQLite and password-hashed local demo accounts. It is for a local SIH demonstration, not a public deployment. Session tokens are random and expire after 12 hours; restart requires sign-in. The provided demo passwords are intentionally public. Live mode verifies each Supabase access token against Auth and fetches current roles from the database. No signup role selection is trusted.

The client supplies GPS coordinates. The distance gate prevents ordinary out-of-radius confirmations but cannot prove physical presence against spoofing. Device integrity, trusted geolocation, abuse analytics and independent-human review are needed before relying on community confidence. The confidence score is a transparent heuristic; it never grants VERIFIED status.

Prototype mutations are serialized within one API worker and database uniqueness protects confirmation/report identities in Supabase. For horizontal scaling, move multi-record workflows and counters into transactional database functions, replace process-local throttling/events with a shared store and add a durable notification outbox. Do not start multiple workers for this demo.

Before operational use: validate Supabase policies in a disposable project, audit privilege and media access, enable HTTPS and a body-size-limiting reverse proxy, configure security headers for the frontend, restrict provider credentials, enable Auth verification and abuse controls, define consent/location/media retention and deletion policies, add log redaction/monitoring, perform provider failure drills, validate models with domain experts, and secure official emergency response agreements.

Current location records are updated only after user action. Coordinates older than one hour are ignored for geofencing; automatic database deletion is not configured. Device-local offline reports and public data caches persist in IndexedDB until synced/cleared. Logout hides private screens; the same account's pending reports are kept for later retry. Do not share the local demo browser profile with untrusted people.
