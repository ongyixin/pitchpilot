# Enterprise Data Handling Policy
**Version 2.1 | Effective: 2025-01-01**

---

## §1 — Data Privacy and Disclosure

### §1.1 Accurate Representation
All public-facing materials, sales pitches, and product demonstrations must accurately
represent how customer data is handled.  Claims about data residency (e.g. "on-device",
"no data leaves your network") must be unambiguously true for **all** deployment
configurations, including optional features.

If an optional feature involves data leaving the customer's environment, this must be
disclosed with explicit opt-in language.

### §1.2 Data Residency
Default deployments must keep all inference and processing data on-premises or within
the customer's designated cloud region.  Optional cloud-sync or telemetry features must
be disabled by default and require explicit customer consent.

---

## §2 — Service Level Agreements

### §2.1 Standard Enterprise SLA
The standard enterprise tier guarantees **99.5 % monthly uptime**.
Premium tiers (as defined in Addendum v2) may offer up to 99.9 %.
Sales and marketing materials must not promise SLA levels that exceed the tier
being presented unless the premium tier is explicitly referenced.

### §2.2 SLA Addendum v2 — Enterprise Standard Tier
- Standard: 99.5 % monthly uptime, 4-hour response SLA
- Professional: 99.8 % monthly uptime, 2-hour response SLA
- Enterprise Premium: 99.9 % monthly uptime, 30-minute response SLA

---

## §3 — Automation and Human Oversight

### §3.1 Automated Decision Systems
Products that use machine learning to produce outputs that influence business decisions
must clearly communicate the role of automation and any confidence thresholds applied.

### §3.2 Human Oversight Requirement
For any automated output with a model confidence score above **0.95**, a human review
step must be available and documented.  Claiming "fully automated — no manual review
required" is only permissible if the product is demonstrably not subject to §3.2 thresholds
(i.e. does not produce high-confidence actionable decisions without oversight options).

---

## §4 — Competitive Claims

### §4.1 Benchmark Integrity
Performance comparisons (speed, accuracy, cost) must reference a named competitor and
a publicly reproducible benchmark.  Unanchored claims such as "3× faster than the
competition" without citation are prohibited in customer-facing materials.

### §4.2 Currency
Benchmarks must have been run within the last 12 months.

---

## §5 — Security and Compliance Certifications

### §5.1 Certification Claims
Only claim certifications that have been formally awarded and are currently in good
standing.  Pending audits (e.g. "SOC 2 in progress") must be disclosed as such.

### §5.2 GDPR / Data Protection
Products processing EU personal data must comply with GDPR.  In particular, Article 22
(automated individual decision-making) applies when the product makes decisions with
legal or similarly significant effects without human review.
