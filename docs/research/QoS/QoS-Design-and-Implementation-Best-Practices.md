# UniFi Quality of Service (QoS) and Smart Queue Management: Design and Implementation Best Practices

## Executive Summary

This report provides a comprehensive technical framework for implementing Quality of Service (QoS) and Smart Queue Management (SQM) on UniFi infrastructure. It addresses the critical design decisions network engineers face when deploying QoS across mixed-use environments—including VoIP, video conferencing, gaming, streaming, and bulk transfers—and presents a reusable library of QoS profile archetypes suitable for IaC-style templating across multiple deployments.

**Key Recommendations Summary:**


| Deployment Scenario | Primary Mechanism | Rate Cap | Key Consideration |
| :-- | :-- | :-- | :-- |
| WAN < 300 Mbps | Smart Queues (fq_codel) | 85–95% of tested line rate | Eliminates bufferbloat; ~5% CPU overhead |
| WAN 300 Mbps – 1 Gbps | Policy-based QoS or SQM (situational) | N/A or 90–95% | Hardware offload disabled with QoS rules; test throughput impact |
| WAN > 1 Gbps | DSCP/CoS-only + VLAN segmentation | None at gateway | QoS rules cause 25–45% throughput reduction[web: 1][web: 35] |
| Dedicated voice/AV | VLAN + DSCP EF 46 + switch port priority | Per-application | End-to-end marking consistency required |


***

## 1. Conceptual Model: UniFi QoS Building Blocks

### 1.1 Smart Queues (SQM with fq_codel)

Smart Queues implement the **fq_codel (FlowQueue Controlled Delay)** algorithm at the WAN edge[web: 10][web: 12]. This mechanism:

- **Isolates flows** using a hashing scheme and schedules them via Deficit Round-Robin (DRR)
- **Automatically manages queue depth** to minimize latency under load
- **Provides implicit priority** for sparse (low-bandwidth) flows over bulk transfers
- **Shifts the bottleneck** from ISP equipment to the local gateway, where intelligent queue management can occur[web: 10]

Ubiquiti explicitly recommends Smart Queues **only for connections below 300 Mbps**[web: 5][web: 45]. On modern hardware (UCG-Fiber, UDM-Pro, UDM-SE, UXG-Pro), testing demonstrates effective operation at gigabit speeds with minimal CPU overhead, though the 300 Mbps warning persists in the UI[web: 10][web: 51].

**fq_codel vs. CAKE:** UniFi currently implements fq_codel exclusively; CAKE (Common Applications Kept Enhanced) is not available despite community feature requests[web: 20]. CAKE offers additional capabilities including per-host fairness, ACK filtering, and simplified link-layer compensation, but requires ~30% more CPU resources[web: 108].

### 1.2 QoS Rules (Policy Engine)

UniFi Network 9.x introduced gateway-based QoS rules via the Policy Engine, offering three objectives[web: 1]:


| Objective | Function | Use Case |
| :-- | :-- | :-- |
| **Prioritize** | Moves traffic to higher-priority queue | Voice, video conferencing, gaming |
| **Limit** | Enforces maximum up/down bandwidth | Backup traffic, software updates, guest networks |
| **Prioritize and Limit** | Combines priority with bandwidth ceiling | Guaranteed bandwidth for critical apps with caps |

**Critical Constraint:** Enabling any QoS rule **disables hardware offloading** on the gateway, reducing throughput by **24–45% for traffic exceeding 1 Gbps**[web: 1][web: 31][web: 35]. This applies globally—not just to traffic matched by rules.

### 1.3 Switch Port QoS: DSCP/CoS and Queue Assignment

UniFi switches support Layer 2/3 QoS through port-level configuration[web: 1][web: 18]:

- **Match Type:** DSCP value, IP Precedence, or None (all traffic)
- **Remark Traffic:** Optionally rewrite DSCP or CoS on egress
- **Queue Assignment:** Map matched traffic to queues 0–7 (0 = lowest, 7 = highest priority)

For Pro/Enterprise switches, **Pro AV profiles** provide pre-configured DSCP/CoS mappings for Dante, Q-SYS, SDVoE, NDI, AES67, and Shure environments[web: 18][web: 94].

### 1.4 WiFi QoS (WMM) and Speed Limits

**WMM (Wi-Fi Multimedia)** provides airtime-based prioritization using four access categories[web: 117]:


| Access Category | 802.1p Priority | Traffic Type | DSCP Mapping |
| :-- | :-- | :-- | :-- |
| AC_VO (Voice) | 6, 7 | VoIP, real-time | EF (46), CS6, CS7 |
| AC_VI (Video) | 4, 5 | Video streaming, conferencing | AF41 (34), CS4, CS5 |
| AC_BE (Best Effort) | 0, 3 | Default web, email | CS0 (0), AF2x |
| AC_BK (Background) | 1, 2 | Bulk transfers, updates | CS1, AF1x |

UniFi APs honor DSCP markings and map EF (46) traffic to WMM voice priority by default[web: 77]. **WiFi Speed Limits** are per-client bandwidth caps applied at the AP level—distinct from QoS prioritization[web: 70].

### 1.5 Trust Boundaries and DSCP Handling

A **trust boundary** defines where the network honors or overwrites incoming DSCP/CoS markings[web: 55]. Best practices:

- **Trust controlled devices** (IP phones, managed endpoints) at the access layer
- **Do not trust PC traffic** passively—remark or assign default markings
- **Maintain consistent marking** end-to-end; avoid gratuitous re-marking in the core[web: 55]

***

## 2. Design Principles and Decision Framework

### 2.1 Decision Tree: When to Use Which Mechanism

```
┌─────────────────────────────────────────────────────────────┐
│                    WAN Bandwidth Assessment                 │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
         < 300 Mbps     300 Mbps–1 Gbps    > 1 Gbps
              │               │               │
              ▼               ▼               ▼
     ┌────────────────┐ ┌───────────────┐ ┌─────────────────────┐
     │ Smart Queues   │ │ Hybrid/Test   │ │ DSCP/VLAN Only      │
     │ (Primary)      │ │ SQM or Policy │ │ No gateway shaping  │
     └────────────────┘ └───────────────┘ └─────────────────────┘
              │               │               │
              ▼               ▼               ▼
     Additional controls if  Measure HW      Trust DSCP at switches;
     needed: policy-based    offload impact  shape only at true
     QoS for specific apps   before deploy   bottleneck (ISP modem)
```


### 2.2 Smart Queues Rate Selection

**Methodology for determining optimal SQM rates:**

1. **Baseline measurement:** Run multiple speed tests without SQM at different times; record consistent achievable rates
2. **Initial configuration:** Set down/up rates to **85–90% of measured speeds**[web: 5][web: 64]
3. **Bufferbloat validation:** Test at [waveform.com/tools/bufferbloat](https://www.waveform.com/tools/bufferbloat); target **A+ grade** (< 5ms added latency under load)[web: 132][web: 135]
4. **Iterative tuning:** Increase rates in 2–5% increments until bufferbloat grade degrades; step back one increment

**Reference tuning example (1 Gbps fiber):**[web: 10]


| Stage | SQM Caps (Down/Up) | Achieved Speed | Latency Under Load |
| :-- | :-- | :-- | :-- |
| Baseline (No SQM) | N/A | 1,055/960 Mbps | Download: 89ms, Upload: 7ms |
| Conservative | 950/900 Mbps | 863/817 Mbps | 4ms/4ms |
| Optimized | 1,000/930 Mbps | 909/844 Mbps | 4ms/4ms |

For variable-rate connections (cable, DSL), use **80–85%** to accommodate rate fluctuation[web: 64].

### 2.3 Voice VLAN Design

**Recommended architecture for VoIP deployments:**

1. **Dedicated VLAN:** Create a voice-only VLAN (e.g., VLAN 16) with appropriate IP scope[web: 2][web: 22]
2. **LLDP-MED provisioning:** Enable voice VLAN advertisement on switch ports; compliant phones auto-negotiate VLAN membership[web: 54][web: 59]
3. **DSCP marking:** Phones should mark RTP as **EF (46)**, signaling as **CS3 (24)**[web: 74][web: 9]
4. **Switch port priority:** Assign voice ports to **High** or **Critical** priority; enable DSCP trust[web: 11]
5. **SIP ALG:** **Disable** SIP ALG on the gateway—it typically breaks SIP signaling[web: 34][web: 9]

**Acceptable VoIP thresholds:**[web: 127][web: 131]


| Metric | Acceptable | Optimal |
| :-- | :-- | :-- |
| One-way latency | < 150ms | < 80ms |
| Jitter | < 30ms | < 10ms |
| Packet loss | < 1% | < 0.1% |

### 2.4 Handling Gaming and Interactive Traffic

Gaming and real-time interactive applications benefit from **low and consistent latency** rather than raw bandwidth. Recommended approach:

- **Do not over-prioritize:** Gaming typically generates sparse traffic flows; fq_codel inherently prioritizes sparse flows[web: 105]
- **Smart Queues sufficient:** For sub-300 Mbps links, SQM alone dramatically improves gaming latency[web: 10][web: 57]
- **Explicit prioritization:** If needed, create QoS rules targeting gaming devices or applications with **Prioritize** objective
- **DSCP marking:** Consider marking gaming traffic as **EF (46)** or **AF41** if endpoint supports it[web: 11]


### 2.5 Bulk Traffic De-prioritization

Explicit de-prioritization of bulk transfers (backups, software updates, P2P) is often more effective than trying to prioritize everything else:

- **Limit objective:** Apply bandwidth limits (e.g., 75% of WAN) to file transfer and P2P categories[web: 5]
- **Schedule restrictions:** Apply rules during business hours only; allow full bandwidth overnight
- **Background class:** Mark backup traffic as **AF1x** or **CS1** for background handling

***

## 3. Core Best Practices

### 3.1 Shape Only at the True Bottleneck

**Principle:** QoS shaping is effective only when applied at the actual congestion point—typically the WAN uplink/downlink.

- **Avoid double shaping:** Do not apply Smart Queues at the gateway AND rate limits at the AP for the same traffic
- **ISP equipment:** If ISP modem buffers heavily, shaping must occur before traffic hits that device
- **Internal links:** LAN-side shaping is rarely needed unless specific inter-VLAN bottlenecks exist


### 3.2 Smart Queues Configuration Guidelines

| Guideline | Recommendation | Rationale |
| :-- | :-- | :-- |
| Rate cap | 85–95% of tested WAN speed | Creates artificial bottleneck at gateway where fq_codel manages queues[web: 10][web: 14] |
| Hardware threshold | Not recommended > 300 Mbps (vendor guidance) | CPU-intensive; newer hardware can exceed this[web: 45] |
| Validation | A+ bufferbloat score | Confirms latency under load is < 5ms[web: 132] |
| PPPoE consideration | Test carefully | PPPoE + SQM doubles CPU load; may reduce throughput significantly[web: 10] |

### 3.3 DSCP Marking Standards

| Traffic Class | DSCP Value | PHB | Use Case |
| :-- | :-- | :-- | :-- |
| Voice (RTP) | 46 | EF | VoIP media streams |
| Video conferencing | 34 | AF41 | Zoom, Teams, WebRTC video |
| Call signaling | 24 | CS3 | SIP, H.323, SRTP signaling |
| Streaming media | 26 | AF31 | 4K OTT, adaptive bitrate |
| Network control | 48 | CS6 | Routing protocols, SNMP |
| Best effort | 0 | CS0 | Default web, email |
| Bulk/background | 10 | AF11 | Backups, updates, sync |

**End-to-end consistency:** Configure switches to trust DSCP at ingress ports connected to trusted devices (phones, APs, known endpoints)[web: 55][web: 46].

### 3.4 SIP ALG Handling

**Recommendation:** Disable SIP ALG in all deployments unless explicitly required by VoIP vendor[web: 34][web: 9].

**UniFi path:** Settings → Application Firewall → Firewall Rules → Conntrack Modules → Disable SIP[web: 40]

SIP ALG rewrites SIP headers and often corrupts RTP stream negotiation, causing one-way audio, dropped calls, and registration failures.

### 3.5 Class-Based vs. Application-Based QoS

| Approach | Pros | Cons | Recommendation |
| :-- | :-- | :-- | :-- |
| **Class-based** (VLAN, DSCP, device group) | Deterministic, scalable, DPI-independent | Requires endpoint marking or manual classification | Preferred for enterprise |
| **Application-based** (DPI signatures) | Automatic identification, no endpoint config | DPI CPU overhead, signature lag, encrypted traffic challenges | Supplement only |

**Guidance:** Use VLAN and DSCP as primary classification; supplement with DPI-based rules for specific applications where endpoint marking is impossible[web: 9].

***

## 4. Reference QoS Profile Library

The following profiles represent reusable archetypes for IaC-style deployment templates. Each profile specifies intent, target environment, and UniFi implementation details.

### 4.1 Profile Summary Table

| Profile Name | Traffic Class | Target Environment | Primary Mechanisms | Key UniFi Settings |
| :-- | :-- | :-- | :-- | :-- |
| **VOICE-FIRST** | VoIP | Any with desk phones | Voice VLAN, DSCP EF, switch priority | VLAN + Port Profile + QoS rule (prioritize) |
| **VIDEO-COLLAB** | Video conferencing | Remote work, hybrid office | DSCP AF41, QoS prioritize | QoS rule on Zoom/Teams/Meet |
| **GAMING-INTERACTIVE** | Gaming, remote desktop | Home office, SMB | Smart Queues, sparse flow priority | SQM enabled; optional prioritize rule |
| **STREAMING-MEDIA** | 4K OTT, adaptive streaming | Residential, hospitality | Best effort or AF31 | WiFi speed limit; no explicit priority |
| **BULK-BACKGROUND** | Backups, updates, sync | All environments | De-prioritize, rate limit | QoS rule (limit) on file transfer category |
| **GUEST-BESTEFFORT** | Guest WiFi | Retail, hospitality, office | Isolated VLAN, rate limit | SSID isolation + WiFi speed limit |

### 4.2 Detailed Profile Specifications

#### Profile 1: VOICE-FIRST

**Intent:** Ensure voice calls experience < 150ms latency, < 30ms jitter, and < 1% packet loss regardless of concurrent traffic.

**Target Environment:** SMB office, MSP client sites, any deployment with dedicated VoIP phones.

**Implementation:**


| Component | Configuration |
| :-- | :-- |
| **VLAN** | Dedicated voice VLAN (e.g., VLAN 16); isolate from data |
| **Switch port profile** | Voice VLAN assignment + LLDP-MED enabled |
| **DSCP handling** | Trust DSCP on voice ports; phones mark EF (46) for RTP, CS3 (24) for signaling |
| **Port priority** | High or Critical on voice ports |
| **Gateway QoS** | Prioritize rule targeting voice VLAN or phone IP group |
| **Smart Queues** | Enable if WAN < 300 Mbps |
| **SIP ALG** | Disabled |
| **Firewall** | Allow UDP 5060 (SIP), 10000–20000 (RTP) inbound to voice VLAN |

**Validation:** Place concurrent bulk transfers and VoIP test calls; measure MOS score > 4.0.

***

#### Profile 2: VIDEO-COLLAB

**Intent:** Maintain smooth video conferencing (Zoom, Teams, Meet, WebRTC) during network congestion.

**Target Environment:** Remote workforce, hybrid office, education.

**Implementation:**


| Component | Configuration |
| :-- | :-- |
| **QoS rule** | Prioritize objective; destination: App category "Video Conferencing" |
| **DSCP** | Mark video as AF41 (34) if endpoint supports |
| **Bandwidth burst** | Short (allows brief spikes for video keyframes) |
| **Smart Queues** | Enable if WAN < 300 Mbps |
| **WiFi** | Ensure WMM enabled (default); consider dedicated SSID for corporate devices |

**Note:** Most video conferencing applications adapt bitrate dynamically; prioritization helps during congestion but bandwidth headroom is equally important[web: 80].

***

#### Profile 3: GAMING-INTERACTIVE

**Intent:** Minimize latency and jitter for real-time gaming and remote desktop applications.

**Target Environment:** Home office, residential, creative studios with remote workstations.

**Implementation:**


| Component | Configuration |
| :-- | :-- |
| **Smart Queues** | Primary mechanism; fq_codel inherently prioritizes sparse flows |
| **Rate cap** | 90% of tested WAN speed for stable connections; 85% for variable |
| **QoS rule (optional)** | Prioritize specific gaming consoles or PCs if contention persists |
| **DSCP** | Mark gaming traffic EF (46) if router supports |
| **WiFi** | Prefer 5 GHz; minimize AP hop count; enable band steering |

**Validation:** Run bufferbloat tests during gaming sessions; target A+ grade.

***

#### Profile 4: STREAMING-MEDIA

**Intent:** Deliver consistent 4K streaming without impacting higher-priority traffic.

**Target Environment:** Residential, hospitality, common areas.

**Implementation:**


| Component | Configuration |
| :-- | :-- |
| **Priority** | Best effort (CS0) or AF31 if explicit marking desired |
| **QoS rule** | None or Limit (cap at 50–75% WAN if contention exists) |
| **WiFi speed limit** | Per-client cap if shared environment (e.g., 50 Mbps) |
| **Smart Queues** | Enable; streaming adapts well to available bandwidth |

**Rationale:** Adaptive bitrate streaming (HLS, DASH) handles congestion gracefully; explicit prioritization rarely needed.

***

#### Profile 5: BULK-BACKGROUND

**Intent:** Explicitly de-prioritize backups, software updates, and sync traffic to prevent impact on interactive applications.

**Target Environment:** All environments; particularly effective when combined with voice/video profiles.

**Implementation:**


| Component | Configuration |
| :-- | :-- |
| **QoS rule** | Limit objective; destination: Categories "File Transfer," "Peer-to-Peer," "Software Updates" |
| **Bandwidth cap** | 50–75% of WAN during business hours |
| **Schedule** | Restrict limits to 08:00–18:00 weekdays; full bandwidth overnight |
| **DSCP** | Mark as AF11 (10) or CS1 (8) if endpoint supports |

**Example rule:**

- Objective: Prioritize and Limit
- Download/Upload: 75% of WAN
- Bandwidth burst: Short
- Destination: App categories (File Transfer, Peer-to-Peer, Software Updates)[web: 5]

***

#### Profile 6: GUEST-BESTEFFORT

**Intent:** Provide functional guest access without impacting production traffic or enabling abuse.

**Target Environment:** Retail, hospitality, enterprise visitor networks.

**Implementation:**


| Component | Configuration |
| :-- | :-- |
| **VLAN** | Isolated guest VLAN; enable "Isolate Network" |
| **WiFi** | Dedicated SSID with WiFi speed limit (e.g., 20–50 Mbps per client) |
| **Client isolation** | Device Isolation (ACL) at switch level |
| **mDNS** | Disabled for guest network |
| **Proxy ARP** | Enabled to reduce broadcast traffic |
| **Traffic restrictions** | Block file transfer and P2P categories |
| **QoS** | No prioritization; best effort only |
| **Captive portal** | Optional; consider for liability acknowledgment |

**Aggregate bandwidth (optional):** Use QoS Limit rule on entire guest VLAN to cap total bandwidth (e.g., 25–50% of WAN)[web: 110][web: 113].

***

## 5. Implementation Notes and Pitfalls

### 5.1 Performance Impact by Gateway Model

| Gateway | IDS/IPS Throughput | Smart Queues Impact | QoS Rule Impact |
| :-- | :-- | :-- | :-- |
| USG | 85 Mbps | Significant; ~300 Mbps max | Not recommended |
| USG Pro 4 | 250 Mbps | ~400 Mbps max | Hardware offload disabled |
| UDM | 850 Mbps | Minimal | Throughput reduction likely |
| UDM Pro | 3.5 Gbps | ~5% CPU overhead | 25–45% reduction > 1 Gbps[web: 35] |
| UDM Pro Max | 5 Gbps | Minimal impact | Significant reduction at high rates |
| UDM SE | 3.5 Gbps | Supported | Hardware offload disabled |
| UCG-Fiber | 5 Gbps | Excellent results[web: 10] | Test required |
| UCG-Ultra | 1 Gbps | Supported | Limited headroom |
| UCG-Max | 2.3 Gbps | Supported | Test required |
| UXG-Pro | 3+ Gbps | Dedicated gateway resources | Similar to UDM Pro |

### 5.2 Firmware and Feature Dependencies

- **Smart Queues:** Available on all UniFi gateways; requires UniFi Network 5.x+
- **QoS rules (Policy Engine):** Requires UniFi Network 9.x+; zone-based firewall recommended for 9.4+[web: 4][web: 96]
- **Pro AV profiles:** Requires Network 8.4.59+ and supported switches (Pro/Enterprise lines) with firmware 7.1.26+[web: 18]
- **DSCP switch QoS:** Limited to Pro/Enterprise switches; not available on standard Lite/Flex models[web: 84]


### 5.3 Common Misconfigurations

| Misconfiguration | Symptom | Resolution |
| :-- | :-- | :-- |
| **Double shaping** | Excessive latency, reduced throughput | Shape only at WAN edge; remove AP/VLAN limits if gateway shaping active |
| **DSCP trust mismatch** | Priority not honored; voice quality issues | Verify trust at ingress ports; check end-to-end DSCP handling |
| **Over-prioritization** | Nothing actually prioritized; all traffic equal | Prioritize only truly critical classes; de-prioritize bulk instead |
| **SIP ALG enabled** | One-way audio, dropped calls, registration failures | Disable SIP ALG; verify NAT traversal works without it |
| **Smart Queues on PPPoE** | Severe throughput reduction | Test carefully; PPPoE encapsulation overhead compounds CPU load |
| **QoS rules on high-speed WAN** | 25–45% throughput loss | Use DSCP-only approach for > 1 Gbps; avoid gateway QoS rules |
| **WiFi speed limit vs. QoS confusion** | Bandwidth capped but no prioritization | Speed limits are not QoS; use QoS rules for priority |

### 5.4 Interaction: Per-SSID Limits + QoS Rules + Smart Queues

**Order of operations:**

1. **WiFi speed limits** apply per-client at the AP (air interface)
2. **QoS rules** evaluate at the gateway for WAN-bound traffic
3. **Smart Queues** shape aggregate WAN traffic after all other processing

**Guidance:**

- WiFi speed limits reduce what reaches the gateway; useful for guest containment
- QoS rules classify and queue traffic independent of WiFi limits
- Smart Queues provide aggregate fairness; effective even without explicit rules
- **Avoid redundant limits:** If QoS rule limits a VLAN to 100 Mbps, per-client WiFi limits within that VLAN may be unnecessary

***

## 6. Validation and Operational Guidance

### 6.1 Testing QoS Effectiveness

| Test | Tool/Method | Target Result |
| :-- | :-- | :-- |
| **Bufferbloat** | [waveform.com/tools/bufferbloat](https://www.waveform.com/tools/bufferbloat) | A+ grade (< 5ms latency under load) |
| **VoIP quality** | Synthetic call generator, MOS scoring | MOS > 4.0 under concurrent load |
| **Concurrent transfers** | iperf3 + latency monitoring | Voice/gaming latency stable during bulk transfers |
| **Real-world validation** | Video call + backup running simultaneously | No perceivable quality degradation |

**Flent testing (advanced):**[web: 50][web: 139]

```bash
flent rrul -p all_scaled -H flent-fremont.bufferbloat.net
```

Generates comprehensive latency/throughput charts under Real-time Response Under Load (RRUL) test.

### 6.2 Documentation and Change Control

**Naming conventions for profiles:**


| Element | Convention | Example |
| :-- | :-- | :-- |
| QoS rule | `[ENV]-[CLASS]-[ACTION]` | `SMB-VOICE-PRIORITIZE` |
| VLAN | `[SITE]-[PURPOSE]-[ID]` | `HQ-VOICE-16` |
| Switch port profile | `[CLASS]-PORT` | `VOIP-PORT` |
| WiFi speed limit | `[LIMIT]-[TARGET]` | `50M-GUEST` |

**Version control concepts:**

- Maintain profile definitions in version-controlled JSON/YAML (UniFi API v0.1 supports limited export)[web: 99][web: 102]
- Document baseline configurations per site type (home office, SMB, enterprise)
- Track changes with dated notes: "2025-11-15: Increased SQM cap 900→950 Mbps after ISP upgrade"


### 6.3 Monitoring and Alerting

- **Traffic Flows:** UniFi Network 9.x provides real-time flow visibility (Insights → Flows)[web: 112]
- **DPI statistics:** Deep Packet Inspection identifies application traffic; useful for validating rule matches[web: 85][web: 126]
- **Gateway CPU:** Monitor when Smart Queues or QoS rules active; sustained > 80% indicates hardware limit
- **Bufferbloat regression:** Periodic testing recommended after firmware updates or ISP changes

***

## 7. Conclusion

UniFi provides a layered QoS architecture suitable for deployments ranging from home offices to multi-site MSP templates. The key design decisions center on:

1. **WAN bandwidth determines primary mechanism:** Smart Queues for sub-300 Mbps; policy-based QoS with caution at mid-range speeds; DSCP/VLAN-only for high-throughput environments
2. **Hardware offload tradeoffs are real:** QoS rules disable offloading with significant throughput implications above 1 Gbps
3. **End-to-end consistency matters:** DSCP marking, trust boundaries, and switch queue mapping must align across the entire path
4. **Validation is essential:** Bufferbloat testing, MOS scoring, and real-world concurrent load tests confirm QoS effectiveness

The profile library provided offers a foundation for reusable, IaC-ready templates that can be adapted to specific deployment requirements while maintaining consistent design principles across environments.

[^1]: https://help.ui.com/hc/en-us/articles/204911354-UniFi-QoS-and-Traffic-Shaping

[^2]: https://www.youtube.com/watch?v=qC81HCv2iu8

[^3]: https://community.ui.com/questions/Best-practice-for-QOS/aad93ab4-07a0-4d79-9a0d-cf90e1ed9866

[^4]: https://www.youtube.com/watch?v=a0jI9ZibWpQ

[^5]: https://lazyadmin.nl/home-network/unifi-qos/

[^6]: https://www.youtube.com/watch?v=Pv1Q3iTXCvM

[^7]: https://flore.unifi.it/retrieve/73c02ae3-cf1e-49da-a13b-e6be5521970d/Distributed Services Management over Dynamic Networks of Things_towards%20a%20Unified%20SDN%20oriented%20Design_Michele_Bonanni.pdf

[^8]: https://support.spokephone.com/hc/en-us/articles/360055921132-How-to-set-up-a-QoS-Ubiquiti-UniFi-router-instructions

[^9]: https://viirtue.com/how-to-configure-qos-for-voip-on-ubiquiti-unifi-and-edgerouter-prioritization-ports-and-sip-alg/

[^10]: https://www.reddit.com/r/Ubiquiti/comments/1nqy3bp/ucgfiber_smart_queue_management_sqm_tuning_to/

[^11]: https://www.unihosted.com/blog/how-to-configure-qos-tagging-in-unifi-networks

[^12]: https://www.unihosted.com/blog/the-ultimate-guide-to-setting-up-unifi-smart-queues

[^13]: https://support.hostifi.com/en/articles/10329883-unifi-configuring-qos

[^14]: https://community.ui.com/questions/Recommended-Smart-Queues-Up-and-Downrate/e0f084a1-1e82-446c-838d-98450b055569

[^15]: https://www.scribd.com/document/931183624/Howtoconfigure-QoS-Tagging-in-Unifi

[^16]: https://www.reddit.com/r/Ubiquiti/comments/1b4kucv/how_do_you_handle_qos_with_unifi_routers/

[^17]: https://community.ui.com/questions/Whats-the-state-of-native-fqcodel-on-wifi-and-of-smart-queues-fqcodel-cake/13ac066c-3517-48b9-b781-239009ca06ac

[^18]: https://help.ui.com/hc/en-us/articles/18125733726615-Pro-AV-Traffic-Optimization-on-UniFi-Switches

[^19]: https://dongknows.com/qos-explained-how-quality-of-service-better-wi-fi/

[^20]: https://community.ui.com/questions/Feature-Request-CAKE-qdisc-support-for-Smart-Queues-on-UDM-Pro/25fb36f1-182f-4513-ba1d-893755219d25

[^21]: https://community.ui.com/questions/Smartphones-VoIP-and-WMM-CoS-and-DSCP-requirements/84ac8639-df88-4548-a65c-6e867fbe4f95

[^22]: https://www.youtube.com/watch?v=5Gf2AmTqliY

[^23]: https://www.unihosted.com/blog/mastering-unifi-bandwidth-management-tips-for-throttling-and-prioritizing-devices

[^24]: https://community.ui.com/questions/Recommended-Smart-Queues-Up-and-Downrate/e0f084a1-1e82-446c-838d-98450b055569?page=2

[^25]: https://www.reddit.com/r/networking/comments/o1xzfq/lldp_voice_vlan_and_dscp/

[^26]: https://www.youtube.com/watch?v=8ZrBa0NqFu4

[^27]: https://forum.peplink.com/t/need-active-queue-management-for-bufferbloat-fq-codel/16199

[^28]: https://www.reddit.com/r/Ubiquiti/comments/npr72f/unifi_traffic_shaping_prioritizing_2_wifi_networks/

[^29]: https://community.ui.com/t5/EdgeMAX/802-1p-tagging-CLASSIFY-iptables-target-and-offload/m-p/1412967

[^30]: https://community.ui.com/questions/Limiting-bandwidth-limit-per-group/a4157075-df41-4223-bf52-de705f0df5e3

[^31]: https://www.reddit.com/r/Ubiquiti/comments/1k7i757/udmpro_with_qos_enabled_cant_hit_1gbit_expected/

[^32]: https://documentation.extremenetworks.com/WiNG/7.3.0/WCSRG/GUID-E3278FFF-1523-476B-B588-0CB13FF7E066.shtml

[^33]: https://help.uisp.com/hc/en-us/articles/22591077433879-EdgeRouter-Hardware-Offloading

[^34]: https://www.nextiva.com/blog/disable-sip-alg.html

[^35]: https://www.youtube.com/watch?v=u_Az9L1c4Zg

[^36]: https://community.ui.com/questions/Edgerouter-max-throughput-with-hardware-offload-disabled/15b5aff7-7b29-445f-9925-25b70e98e43b

[^37]: https://support.kixie.com/hc/en-us/articles/360052082493-Disable-SIP-ALG-Ubiquiti-Unifi-Security-Gateway-USG-UNMS

[^38]: https://www.reddit.com/r/Ubiquiti/comments/r0dh9p/unifis_advanced_wifi_settings_explained/

[^39]: https://community.ui.com/questions/USG-QoS-performance/95cc9dc6-620f-4cb7-8b0d-dac100a58b08

[^40]: https://community.ui.com/questions/Ubiquiti-Dream-Router-How-do-I-disable-SIP-ALG-and-DHCP-Option-66-has-been-configured-with-an-IP-ad/8e04e249-8ce8-4ef8-9228-75b91fd6e344

[^41]: https://community.ui.com/questions/QOS-Device-priority/8c6fe73a-9e88-49f7-ba2b-1c4a13f77fa6

[^42]: https://www.reddit.com/r/Ubiquiti/comments/yamgws/smart_queue_qos_throughput_of_udmpro/

[^43]: https://docs.engenius.ai/ews-switch-user-manual/ethernet-switch-features/qos/dscp-mapping

[^44]: https://www.reddit.com/r/tmobileisp/comments/1jbny4y/amazing_bufferbloat_results_with_ubiquiti_ucgfiber/

[^45]: https://help.ui.com/hc/en-us/articles/12648661321367-UniFi-Gateway-Smart-Queues

[^46]: https://community.ui.com/questions/Help-with-DSCP-CoS-on-trunks/9b0d34f0-8bac-4b4a-9c13-21ad77bf3858

[^47]: https://www.reddit.com/r/Ubiquiti/comments/12ir2y4/udm_pro_bufferbloat_is_a_thing_and_how_i_improved/

[^48]: https://community.ui.com/questions/d90fa07f-92c5-40b4-a22a-2a86257f042d

[^49]: https://www.reddit.com/r/Ubiquiti/comments/mufzzd/do_unifi_switches_support_qos/

[^50]: https://www.bufferbloat.net/projects/bloat/wiki/Tests_for_Bufferbloat/

[^51]: https://www.youtube.com/watch?v=C9rtRwPzzzE

[^52]: https://community.ui.com/questions/Question-about-DSCP-and-CoS-in-a-big-layer2-vlan-MST-ubiquiti-network/6a2a7e66-2d9a-47eb-a25c-29d6945d7e5a

[^53]: https://www.waveform.com/tools/bufferbloat

[^54]: https://www.youtube.com/watch?v=jIov8gdG82E

[^55]: https://networkjourney.com/dscp-vs-cos-trust-boundary-network-marking-demystified-for-engineers-ccnp-enterprise/

[^56]: https://community.ui.com/questions/Creating-VLAN-for-IP-Phones-LLDP-MED/9164198b-bcd8-43df-9ff3-5ea3b9a6b9e3

[^57]: https://www.reddit.com/r/Ubiquiti/comments/1cfttez/qostraffic_prioritization_uxgmaxu6pro_minimize/

[^58]: https://community.ui.com/questions/DSCP-marking-on-non-DSCP-device/b26efc24-f8ab-45e1-b4ad-e62c4a9648cc

[^59]: https://documentation.spectrumvoip.com/preparing-to-use-voip-services/recommended-unifi-gateway-configuration-and-firewall-policies

[^60]: https://community.ui.com/questions/Traffic-prioritization-for-Steam-games-on-home-network/a01a46fd-4178-43c8-ac67-415208ac8b6b

[^61]: https://www.reddit.com/r/networking/comments/xrc6v7/dscp_trust_for_voip_qos/

[^62]: https://community.ui.com/questions/Any-practical-difference-between-using-Smart-Queues-and-QoS-limit-prioritize-rules/cb42624f-2f57-417e-ade1-5528e977f450

[^63]: https://community.ui.com/questions/e916e5bd-9362-4c20-8c0d-30d2440bbdc2

[^64]: https://www.reddit.com/r/firewalla/comments/1ettt5t/smart_queue_fq_codel_or_cake/

[^65]: https://www.youtube.com/watch?v=LrwhJjs6VBc

[^66]: https://community.ui.com/questions/QoS-Limits-not-working-in-Unifi-Network-9-4-19/fd232f94-6e4e-4a92-82b7-6a7bee10afc9

[^67]: https://forums.islandrouter.com/topic/121-sqm-fq_codel-or-cake/

[^68]: https://www.reddit.com/r/Ubiquiti/comments/14gyuqu/apply_qos_bandwidth_rules_to_all_clients/

[^69]: https://help.ui.com/hc/en-us/articles/5546542486551-Traffic-Policy-Management-in-UniFi

[^70]: https://www.youtube.com/watch?v=1vq0L-ACeic

[^71]: https://blog.cerowrt.org/post/state_of_fq_codel/

[^72]: https://www.youtube.com/watch?v=KO_jeXLIyE4

[^73]: https://evanmccann.net/blog/unifi-routers-overview

[^74]: https://www.cisco.com/c/en/us/td/docs/voice_ip_comm/uc_system/design/guides/videodg/vidguide/qos.html

[^75]: https://tech-now.io/en/it-support-issues/network/how-to-fix-qos-misconfiguration-step-by-step-guide-to-prioritizing-network-traffic

[^76]: https://ifeeltech.com/unifi-gateway-comparison-guide/

[^77]: https://documentation.meraki.com/Platform_Management/Dashboard_Administration/Design_and_Configure/Architectures_and_Best_Practices/Cisco_Meraki_Best_Practice_Design/Best_Practice_Design_-_MR_Wireless/Wireless_VoIP_QoS_Best_Practices

[^78]: https://hostbor.com/unifi-slow-critical-mistakes-fix/

[^79]: https://www.youtube.com/watch?v=HvUbg6dKhtU

[^80]: https://library.zoom.com/admin-corner/network-management/quality-of-service-and-network-best-practices-explainer/using-dscp-marking-with-zoom

[^81]: https://www.storagereview.com/review/ubiquiti-cloud-gateway-fiber-review-10g-gateway-with-5gbps-ids-ips

[^82]: https://www.cbtnuggets.com/blog/technology/networking/what-is-differentiated-services-code-point-dscp

[^83]: https://www.youtube.com/watch?v=BXM1fWX1cFc

[^84]: https://forums.lawrencesystems.com/t/qos-details-on-ubiquity-switches/17709

[^85]: https://help.ui.com/hc/en-us/articles/12570783535383-UniFi-Gateway-Traffic-and-Device-Identification

[^86]: https://www.stackscale.com/blog/95-percentile-metering-billing-bandwidth/

[^87]: https://support.qsys.com/en_US/awareness/awareness-%7C-quality-of-service-settings-across-qlan-dante-and-aes67

[^88]: https://community.ui.com/releases/UniFi-Network-Application-9-1-119/ae21f6e9-b18a-4705-81c0-cfff86a25bcb

[^89]: https://www.ioriver.io/terms/network-95th-percentile

[^90]: https://www.noction.com/blog/95th-percentile-explained

[^91]: https://service.shure.com/s/article/How-do-I-configure-a-Ubiquiti-switch-with-Shure-networked-devices?language=en_US

[^92]: https://www.facebook.com/UIeverywhere/posts/introducing-unifi-network-91real-time-traffic-flow-visibilitysmarter-qos-for-voi/1093304012826328/

[^93]: https://www.auvik.com/franklyit/blog/95th-percentile-bandwidth-metering/

[^94]: https://techspecs.ui.com/unifi/switching/usw-pro-aggregation?subcategory=all-switching

[^95]: https://securityboulevard.com/2022/07/infrastructure-as-code-iac-a-developers-perspective/

[^96]: https://www.hostifi.com/blog/what-is-new-in-unifi-network-9-4-17

[^97]: https://spacelift.io/blog/infrastructure-as-code-tools

[^98]: https://help.ui.com/hc/en-us/articles/115003173168-Zone-Based-Firewalls-in-UniFi

[^99]: https://www.reddit.com/r/Ubiquiti/comments/1eeyabm/infrastructure_as_code/

[^100]: https://service.shure.com/Service/s/article/How-do-I-configure-a-Ubiquiti-switch-to-work-with-Shure-networked-devices

[^101]: https://community.ui.com/releases/UniFi-Network-Application-9-4-19/6396efa7-0955-4733-a524-f028994f5f50

[^102]: https://community.ui.com/questions/Templating-Site-Deployments-with-Ubiquiti/6cce9d4d-3e55-498b-9f68-4b45c32714cf

[^103]: https://www.youtube.com/watch?v=eLa5LQGA1wU

[^104]: https://community.spiceworks.com/t/guest-network-isolation/101162

[^105]: https://arxiv.org/pdf/1804.07617.pdf

[^106]: https://community.ui.com/questions/Prioritize-Unifi-Traffic-for-specific-devices/cc7ee146-67ea-43ca-abed-f38ea7cd5a0f

[^107]: https://www.guestgate.cloud/blog/how-to-optimize-your-unifi-guest-network/

[^108]: https://www.reddit.com/r/firewalla/comments/1m6m3fb/for_those_of_you_using_cake_under_smart_queue/

[^109]: https://www.reddit.com/r/UNIFI/comments/1p2hod2/what_apps_you_put_in_critical_apps_prioritization/
