# IRP Core Protocol

## An Open Protocol for Client-Side Verifiable AI Inference Billing

**Version:** 0.1.0-draft  
**Status:** Draft  
**Date:** 2026-05-08  
**Authors:** IRP Working Group  

---

## Abstract

The Inference Receipt Protocol (IRP) is an open, client-side verifiable protocol for AI inference service billing and audit. IRP addresses a fundamental asymmetry in the AI inference market: providers unilaterally report token counts and costs, leaving clients with no mechanism to independently verify charges. This opacity enables over-billing, prevents meaningful cost comparison across providers, and obstructs regulatory compliance.

IRP introduces a signed Receipt data structure that accompanies every inference response, containing cryptographically attested token counts, latency metrics, and cost breakdowns. Clients verify Receipts independently using local token counters and Ed25519 signature validation. The protocol defines a framed message format for discovery, handshake, request submission, and response delivery, with explicit error semantics and retry policies. IRP is transport-agnostic and designed to operate over HTTP/1.1, HTTP/2, and HTTP/3, as well as direct TCP or WebSocket connections.

This document specifies the core protocol: message formats, frame types, procedures, error codes, versioning, and security considerations. Companion documents define QoS profiles, metering and audit log schemas, authentication and discovery mechanisms, extension registries, and conformance test vectors.

---

## Status of This Document

This document is a **Draft v0.1** of the IRP Core Protocol specification. It has been produced by the IRP Working Group and is intended for community review and early implementation feedback.

This draft is subject to change. Implementers SHOULD NOT assume backward compatibility between draft revisions. Stable version negotiation is defined in [Section 12](#12-versioning); implementations MUST support version negotiation and MUST gracefully reject unsupported versions.

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://tools.ietf.org/html/rfc2119) and [RFC 8174](https://tools.ietf.org/html/rfc8174) when, and only when, they appear in all capitals, as shown here.

---

## Copyright Notice

Copyright (c) 2026 IRP Working Group

Permission is hereby granted, free of charge, to any person obtaining a copy of this specification and associated documentation files (the "Specification"), to deal in the Specification without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Specification, and to permit persons to whom the Specification is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Specification.

THE SPECIFICATION IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SPECIFICATION OR THE USE OR OTHER DEALINGS IN THE SPECIFICATION.

---

## Table of Contents

1. [Introduction](#1-introduction)
   1.1 [Motivation](#11-motivation)
   1.2 [Design Goals](#12-design-goals)
   1.3 [Non-Goals](#13-non-goals)
2. [Conventions and Terminology](#2-conventions-and-terminology)
   2.1 [RFC 2119 Keywords](#21-rfc-2119-keywords)
   2.2 [Actors](#22-actors)
   2.3 [Core Terms](#23-core-terms)
3. [Architecture](#3-architecture)
   3.1 [Layered Model](#31-layered-model)
   3.2 [Request-Response Flow](#32-request-response-flow)
4. [Protocol Overview](#4-protocol-overview)
   4.1 [Message Lifecycle](#41-message-lifecycle)
   4.2 [State Machine](#42-state-machine)
5. [Frame Format](#5-frame-format)
   5.1 [Frame Header](#51-frame-header)
   5.2 [Frame Types](#52-frame-types)
   5.3 [Body Encoding](#53-body-encoding)
   5.4 [Transport Mapping](#54-transport-mapping)
6. [Procedures](#6-procedures)
   6.1 [Capability Discovery](#61-capability-discovery)
   6.2 [Handshake](#62-handshake)
   6.3 [Request Submission](#63-request-submission)
   6.4 [Response with Receipt](#64-response-with-receipt)
   6.5 [Error Handling](#65-error-handling)
   6.6 [Retry Semantics](#66-retry-semantics)
7. [Error Codes](#7-error-codes)
   7.1 [Protocol Errors (1000-1999)](#71-protocol-errors-1000-1999)
   7.2 [Authentication Errors (2000-2999)](#72-authentication-errors-2000-2999)
   7.3 [Quota and Rate-Limit Errors (3000-3999)](#73-quota-and-rate-limit-errors-3000-3999)
   7.4 [Receipt and Verification Errors (4000-4999)](#74-receipt-and-verification-errors-4000-4999)
   7.5 [Server Errors (5000-5999)](#75-server-errors-5000-5999)
   7.6 [Reserved Ranges](#76-reserved-ranges)
8. [Versioning](#8-versioning)
   8.1 [Version Format](#81-version-format)
   8.2 [Version Negotiation](#82-version-negotiation)
   8.3 [Deprecation Lifecycle](#83-deprecation-lifecycle)
9. [Security Considerations](#9-security-considerations)
   9.1 [Threat Model](#91-threat-model)
   9.2 [Mitigations](#92-mitigations)
   9.3 [Cryptographic Requirements](#93-cryptographic-requirements)
10. [IANA Considerations](#10-iana-considerations)
    10.1 [HTTP Header Field Registry](#101-http-header-field-registry)
    10.2 [Frame Type Registry](#102-frame-type-registry)
    10.3 [Error Code Registry](#103-error-code-registry)
    10.4 [Capability Identifier Registry](#104-capability-identifier-registry)
    10.5 [QoS Class Identifier Registry](#105-qos-class-identifier-registry)
11. [References](#11-references)
    11.1 [Normative References](#111-normative-references)
    11.2 [Informative References](#112-informative-references)

---

## 1. Introduction

### 1.1 Motivation

The AI inference industry has grown into a multi-billion-dollar market with a fundamental structural problem: **billing opacity**. When a client sends a request to an AI inference provider, the provider unilaterally determines:

- How many input tokens were consumed
- How many output tokens were generated
- What the total cost should be
- What latency was experienced

The client has no independent mechanism to verify any of these claims. This asymmetry creates several concrete harms:

1. **Over-billing risk**: A provider can inflate token counts or apply incorrect pricing tiers. The client cannot detect this without manual audit, which is impractical at scale.

2. **Cost comparison obstruction**: Without verifiable metrics, clients cannot meaningfully compare providers on a cost-per-unit basis. The "unit" itself is provider-defined and unverifiable.

3. **Regulatory non-compliance**: The EU AI Act (effective August 2026) requires audit logging and downstream information transmission for high-risk AI systems. China's GB 45438-2025 mandates transparency in AI service billing. Current APIs provide no standardized mechanism for these requirements.

4. **Vendor lock-in**: API format fragmentation and opaque billing make switching providers expensive and risky.

Existing solutions are inadequate:

- **OpenAI-compatible APIs** standardize the request/response format but not the billing verification mechanism.
- **API aggregation platforms** (e.g., OpenRouter, LiteLLM) provide unified access but do not solve the fundamental verification problem; they merely add another opaque layer.
- **TEE (Trusted Execution Environment)** attestation verifies the inference environment but does not provide client-verifiable billing receipts.
- **ZK (Zero-Knowledge) proofs** offer strong cryptographic guarantees but are research-grade and not yet practical for real-time inference.

IRP fills this gap by defining a lightweight, cryptographically verifiable receipt mechanism that operates at the protocol layer, independent of the underlying model or inference engine.

### 1.2 Design Goals

IRP is designed with the following goals, ordered by priority:

1. **Client verifiability**: The client MUST be able to independently verify token counts, costs, and receipt authenticity without trusting the provider.

2. **Minimal overhead**: The protocol MUST add negligible latency and bandwidth overhead to inference requests. Receipt generation and verification MUST complete in under 10 milliseconds.

3. **Transport agnosticism**: The protocol MUST operate over HTTP/1.1, HTTP/2, HTTP/3, and direct TCP or WebSocket connections without modification to the core semantics.

4. **Backward compatibility**: The protocol MUST be incrementally adoptable. A provider can add IRP support to an existing OpenAI-compatible API without breaking existing clients.

5. **Regulatory alignment**: The protocol MUST support the audit logging and transparency requirements of the EU AI Act, China's GB 45438-2025, and comparable regulations.

6. **Extensibility**: The protocol MUST support capability negotiation and extension mechanisms so that new features (e.g., new QoS classes, new signature schemes) can be added without protocol revision.

7. **Implementation simplicity**: A reference implementation MUST fit in under 1000 lines of Python. The protocol MUST be implementable by a single developer in a day.

### 1.3 Non-Goals

The following are explicitly out of scope for IRP Core:

1. **Model quality verification**: IRP verifies billing claims, not model correctness or output quality. A provider can return garbage output with a valid receipt.

2. **Real-time payment settlement**: IRP defines receipts and audit logs, not payment channels or cryptocurrency settlement. Payment is out of scope.

3. **Model intellectual property protection**: IRP does not protect model weights or training data. TEE and confidential computing are complementary technologies.

4. **Universal model API standardization**: IRP does not standardize the content of inference requests or responses. It wraps existing APIs (OpenAI-compatible, Anthropic, etc.) with a verification layer.

5. **Provider reputation or rating**: IRP provides verifiable metrics but does not define reputation systems or provider scoring.

6. **Guaranteed fairness in pricing**: IRP makes pricing transparent and verifiable but does not regulate what prices providers may charge.

---

## 2. Conventions and Terminology

### 2.1 RFC 2119 Keywords

This specification uses the normative keywords defined in [RFC 2119](https://tools.ietf.org/html/rfc2119) and clarified in [RFC 8174](https://tools.ietf.org/html/rfc8174):

- **MUST / REQUIRED / SHALL**: Absolute requirement. Non-compliance breaks interoperability or security.
- **MUST NOT / SHALL NOT**: Absolute prohibition.
- **SHOULD / RECOMMENDED**: Strong recommendation. Valid reasons may exist to deviate, but the full implications must be understood.
- **SHOULD NOT / NOT RECOMMENDED**: Strong discouragement. Valid reasons may exist, but the full implications must be understood.
- **MAY / OPTIONAL**: Truly optional. Interoperability must not depend on the feature.

These keywords appear in ALL CAPS throughout this document. Lowercase uses of these words are non-normative.

### 2.2 Actors

The IRP protocol involves three primary actors:

#### 2.2.1 Client

The **Client** is the entity that initiates inference requests and receives Receipts. The Client:

- Generates requests containing prompt data and desired parameters.
- Requests IRP Receipts by including the appropriate capability indicator.
- Verifies Receipts independently using local token counting and signature validation.
- Maintains an audit log of verified Receipts for dispute resolution and regulatory compliance.
- MAY be an end-user application, a middleware service, or an automated agent.

The Client MUST have access to a token counting implementation compatible with the model being queried. The Client SHOULD maintain a local cache of provider public keys for signature verification.

#### 2.2.2 Provider

The **Provider** is the entity that performs inference and issues signed Receipts. The Provider:

- Advertises its capabilities, including supported models, QoS classes, pricing, and IRP version support.
- Performs inference on client requests.
- Generates and signs Receipts containing actual token counts, latency metrics, and cost data.
- Returns Receipts alongside inference responses.
- Maintains an append-only audit log of all issued Receipts (typically as a Merkle tree).
- MAY be a cloud inference service, a self-hosted model, or an edge device.

The Provider MUST possess an Ed25519 key pair for signing Receipts. The Provider MUST make its public key available through the discovery mechanism defined in [Section 6.1](#61-capability-discovery).

#### 2.2.3 Auditor

The **Auditor** is an optional third-party entity that verifies the integrity of the Provider's audit log and adjudicates disputes. The Auditor:

- Receives periodic snapshots of the Provider's Merkle tree root hash.
- Verifies that Receipts presented by Clients exist in the Provider's log.
- Issues attestation statements about log integrity.
- MAY be engaged by the Client, the Provider, or a regulatory authority.

The Auditor is not involved in the real-time request/response path. Audit is an offline or asynchronous process.

### 2.3 Core Terms

#### 2.3.1 Receipt

A **Receipt** is a cryptographically signed data structure that attests to the resources consumed by a single inference request. A Receipt contains:

- Request identifier and timestamp
- Provider and model identifiers
- Input, output, and total token counts
- Latency metrics (queue time, time-to-first-token, total time)
- Cost breakdown (input cost, output cost, total cost, currency)
- Cryptographic signature over a canonical representation of the above
- Optional content hashes for input and output integrity verification

The Receipt schema is defined in detail in the [Metering & Audit Log](./irp-metering.md) companion document. Conformance test vectors are defined in the [Conformance Profile](./irp-conformance.md).

#### 2.3.2 Frame

A **Frame** is the unit of wire-format message exchange in IRP. Every Frame consists of a fixed-size header followed by a variable-length body. Frames are used for all protocol communication: requests, responses, receipts, errors, and keepalives.

The Frame format is specified in [Section 5](#5-frame-format).

#### 2.3.3 Capability

A **Capability** is a named feature or extension that a Provider advertises as supported. Capabilities are identified by ASCII strings (e.g., `irp.receipt.v1`, `irp.qos.realtime`, `irp.streaming`). The Client and Provider negotiate a common set of Capabilities during the Handshake procedure ([Section 6.2](#62-handshake)).

Capabilities enable incremental adoption: a Provider can support basic IRP receipts without supporting QoS negotiation or streaming.

#### 2.3.4 QoS Class

A **QoS Class** (Quality of Service Class) is a predefined service level that characterizes the latency and availability guarantees for an inference request. IRP Core defines five standard QoS Classes:

| Class | Identifier | Target Latency | Use Case |
|-------|-----------|----------------|----------|
| Realtime | `realtime` | < 100 ms | Voice assistants, live interaction |
| Interactive | `interactive` | < 1 s | Chatbots, coding assistants |
| Standard | `standard` | < 10 s | General purpose inference |
| Batch | `batch` | < 5 min | Background processing |
| Background | `background` | < 1 hour | Large-scale data processing |

Detailed QoS definitions, including SLAs, pricing multipliers, and fallback behavior, are specified in the [QoS Profile](./irp-qos.md) companion document.

#### 2.3.5 Stream

A **Stream** is a logical bidirectional channel between a Client and Provider, identified by a 32-bit `stream_id`. Multiple Streams MAY be multiplexed over a single transport connection. Stream 0 is reserved for control messages (discovery, handshake, errors). Odd-numbered stream IDs are Client-initiated; even-numbered stream IDs are Provider-initiated.

#### 2.3.6 Audit Log

An **Audit Log** is an append-only, tamper-evident record of all Receipts issued by a Provider. The canonical implementation uses a Merkle tree, where each leaf is the hash of a canonicalized Receipt, and the root hash is periodically published or submitted to an Auditor.

The Audit Log schema and Merkle tree construction are defined in the [Metering & Audit Log](./irp-metering.md) companion document.

#### 2.3.7 Token Count

A **Token Count** is the number of tokens consumed or produced by an inference request. Tokens are model-specific units of text processing. IRP does not standardize tokenization algorithms; instead, it requires Providers to declare the tokenizer used and Clients to use a compatible local tokenizer for verification.

The acceptable difference between Provider-reported and Client-computed token counts is defined by the `threshold_percent` parameter, defaulting to 5.0%.

---

## 3. Architecture

### 3.1 Layered Model

IRP is organized into four conceptual layers, each building on the layer below:

```
+-------------------------------------------------------------+
|                        AUDIT LAYER                          |
|  Merkle tree log, periodic attestation, dispute resolution  |
|              [Metering & Audit Log Profile]                 |
+-------------------------------------------------------------+
|                       SIGNING LAYER                         |
|  Ed25519 receipt signatures, key distribution, rotation     |
+-------------------------------------------------------------+
|                      METERING LAYER                         |
|  Token counting, latency measurement, cost calculation      |
|              [QoS Profile, Metering Profile]                |
+-------------------------------------------------------------+
|                      TRANSPORT LAYER                        |
|  Framing, multiplexing, flow control, error handling        |
|         [HTTP/1.1, HTTP/2, HTTP/3, WebSocket, TCP]          |
+-------------------------------------------------------------+
```

**Transport Layer**: Responsible for delivering Frames between Client and Provider. This specification defines how IRP Frames map to HTTP requests/responses, but the protocol is not bound to HTTP. The Transport Layer handles connection management, multiplexing (when supported by the underlying protocol), and basic error propagation.

**Metering Layer**: Responsible for measuring and reporting resource consumption. This includes token counting (input, output, cached, reasoning), latency measurement (queue time, time-to-first-token, inter-token latency, total time), and cost calculation (per-token pricing, QoS multipliers, currency conversion). The Metering Layer is where the Receipt payload is assembled.

**Signing Layer**: Responsible for cryptographically attesting to Receipt integrity. Every Receipt MUST be signed by the Provider using Ed25519. The Signing Layer also handles key distribution (via the discovery mechanism) and key rotation. The canonical serialization for signing is defined to ensure deterministic signatures across implementations.

**Audit Layer**: Responsible for long-term integrity and dispute resolution. The Provider maintains an append-only Merkle tree of all issued Receipts. The root hash is periodically published or submitted to an Auditor. Clients can verify that their Receipts are included in the Provider's log, preventing retroactive deletion or modification.

### 3.2 Request-Response Flow

The following diagram illustrates a complete IRP interaction:

```
+--------+                              +----------+
| Client |                              | Provider |
+--------+                              +----------+
    |                                         |
    |  1. DISCOVERY                           |
    |  GET /.well-known/irp-configuration      |
    |---------------------------------------->|
    |     {capabilities, versions, models,    |
    |      public_key, pricing}               |
    |<----------------------------------------|
    |                                         |
    |  2. HANDSHAKE (optional over HTTP)      |
    |  POST /irp/handshake                    |
    |     {version, capabilities, qos_class}  |
    |---------------------------------------->|
    |     {session_id, confirmed_caps,        |
    |      server_nonce}                      |
    |<----------------------------------------|
    |                                         |
    |  3. REQUEST                             |
    |  POST /v1/chat/completions              |
    |  Headers: X-IRP-Request: true           |
    |           X-IRP-Version: 0.1            |
    |  Body: {model, messages, ...}           |
    |---------------------------------------->|
    |                                         |
    |  4. INFERENCE                           |
    |     [Provider processes request]        |
    |     [Provider counts tokens]            |
    |     [Provider measures latency]         |
    |     [Provider calculates cost]          |
    |     [Provider signs receipt]            |
    |                                         |
    |  5. RESPONSE + RECEIPT                  |
    |  200 OK                                 |
    |  Headers: X-IRP-Request-ID: <uuid>      |
    |           X-IRP-Signature: <base64>     |
    |           X-IRP-Input-Tokens: 42        |
    |           X-IRP-Output-Tokens: 128      |
    |           X-IRP-Total-Tokens: 170       |
    |           X-IRP-Cost-Total: 0.0025      |
    |           X-IRP-Public-Key: <base64>    |
    |  Body: {choices, usage, ...}            |
    |<----------------------------------------|
    |                                         |
    |  6. CLIENT VERIFICATION                 |
    |  [Count tokens locally]                 |
    |  [Verify signature with public key]     |
    |  [Compare counts within threshold]      |
    |  [Store receipt in audit log]           |
    |                                         |
    |  7. AUDIT (async)                       |
    |  [Submit receipt to auditor]            |
    |  [Verify Merkle inclusion proof]        |
    |<--------------------------------------->|
```

Steps 1 and 2 (Discovery and Handshake) are performed once per session or periodically (e.g., daily). Steps 3-6 are performed for every inference request. Step 7 is performed asynchronously, typically batched.

---

## 4. Protocol Overview

### 4.1 Message Lifecycle

Every IRP interaction follows a well-defined lifecycle with five phases:

#### 4.1.1 Discovery

The Client queries the Provider's capability endpoint to determine:

- Supported IRP protocol versions
- Supported capabilities (receipts, QoS classes, streaming, etc.)
- Available models and their versions
- Provider's Ed25519 public key for receipt verification
- Pricing information (per-token rates, QoS multipliers)
- Current service status and any announced maintenance windows

Discovery MAY be cached by the Client. The cache TTL is Provider-defined but MUST NOT exceed 86400 seconds (24 hours). The Client SHOULD re-discover when a request fails with an error indicating capability mismatch.

#### 4.1.2 Handshake

The Client and Provider negotiate a shared protocol configuration for the session. The Handshake:

- Confirms the protocol version to use (highest mutually supported)
- Negotiates the set of active capabilities
- Selects the QoS Class for the session (or confirms per-request QoS selection)
- Exchanges nonces for replay protection
- Establishes a session identifier for correlation

The Handshake is OPTIONAL for HTTP-based transports when per-request headers carry all necessary context. For persistent connections (WebSocket, direct TCP), the Handshake MUST be performed before any inference requests.

#### 4.1.3 Request

The Client submits an inference request. The request:

- Includes the standard inference payload (model, messages, parameters)
- Signals IRP support via the `X-IRP-Request` header or Frame flag
- MAY specify a QoS Class override for this specific request
- MAY include a client-generated nonce for request correlation

#### 4.1.4 Response

The Provider processes the request and returns:

- The standard inference response (generated text, embeddings, etc.)
- An IRP Receipt in headers or a dedicated RECEIPT frame
- Error information if the request could not be satisfied

For streaming responses, the Receipt MAY be delivered in a final RECEIPT frame after all content frames, or MAY be delivered incrementally with partial receipts.

#### 4.1.5 Audit

After receiving the Receipt, the Client:

- Verifies the signature using the Provider's public key
- Counts tokens locally and compares with the Receipt
- Checks that latency and cost figures are within expected bounds
- Stores the Receipt and verification result in a local audit log
- Periodically submits Receipts to an Auditor for Merkle inclusion verification

### 4.2 State Machine

A Client connection to a Provider progresses through the following states:

```
                    +-----------+
                    |   IDLE    |
                    +-----------+
                          |
                          | connect
                          v
                    +-----------+
                    | DISCOVER  |<------------------+
                    +-----------+                    |
                          |                        |
                          | discovery success      | discovery fail (retry)
                          v                        |
                    +-----------+                  |
                    | HANDSHAKE |------------------+
                    +-----------+  handshake fail (retry)
                          |
                          | handshake success
                          v
                    +-----------+
                    |  ACTIVE   |<------------------+
                    +-----------+                    |
                     /     |     \                  |
                    /      |      \                 |
         request   /       |       \  receipt error |
                  v        |        v                |
            +--------+     |   +----------+          |
            | AWAITING |---+   | VERIFYING|          |
            | RESPONSE |       +----------+          |
            +--------+            |                  |
                                  | verify fail      |
                                  v                  |
                            +----------+             |
                            | DISPUTE  |-------------+
                            +----------+
                                  |
                                  | connection close / timeout
                                  v
                            +----------+
                            |  CLOSED  |
                            +----------+
```

**State Definitions:**

- **IDLE**: No connection exists. The Client has not initiated communication.
- **DISCOVER**: The Client has sent a discovery request and is awaiting the response.
- **HANDSHAKE**: The Client has sent a handshake request and is awaiting confirmation.
- **ACTIVE**: The connection is established and ready for inference requests.
- **AWAITING RESPONSE**: The Client has submitted an inference request and is awaiting the response.
- **VERIFYING**: The Client has received a response with a Receipt and is performing verification.
- **DISPUTE**: Receipt verification failed. The Client MAY retry the request, escalate to audit, or mark the Provider as unreliable.
- **CLOSED**: The connection has been terminated. The Client MAY re-enter DISCOVER to establish a new connection.

---

## 5. Frame Format

IRP defines a binary framing layer that is transport-agnostic. When carried over HTTP, Frames map to HTTP requests and responses as described in [Section 5.4](#54-transport-mapping).

### 5.1 Frame Header

Every Frame begins with a fixed 13-byte header:

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|     Magic ('I' 'R' 'P')     |    Version    |   Frame Type   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                          Stream ID                            |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|            Payload Length             |        Flags          |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

**Field Definitions:**

| Field | Offset | Size | Description |
|-------|--------|------|-------------|
| Magic | 0 | 3 bytes | ASCII "IRP" (0x49 0x52 0x50). Identifies the frame as IRP. |
| Version | 3 | 1 byte | Protocol version. High nibble = major, low nibble = minor. Version 0.1 = 0x01. |
| Frame Type | 4 | 1 byte | Identifies the frame purpose. See [Section 5.2](#52-frame-types). |
| Stream ID | 5 | 4 bytes | Unsigned 32-bit integer identifying the logical stream. Network byte order (big-endian). |
| Payload Length | 9 | 3 bytes | Unsigned 24-bit integer specifying the body length in bytes. Max = 16,777,215 bytes (16 MiB - 1). Network byte order. |
| Flags | 12 | 1 byte | Bit flags modifying frame semantics. See below. |

**Total Header Size: 13 bytes**

**Flags Bit Definitions:**

| Bit | Name | Description |
|-----|------|-------------|
| 0x01 | FIN | Final frame in this stream. Set on the last frame of a message. |
| 0x02 | ACK | Acknowledgment requested. Receiver SHOULD respond with a PONG or acknowledgment frame. |
| 0x04 | ERR | Error indicator. Set when this frame carries error information. |
| 0x08 | COMPRESSED | Payload is compressed. Compression algorithm is negotiated in handshake (default: none). |
| 0x10 | ENCRYPTED | Payload is encrypted. Encryption scheme is negotiated in handshake (default: none). |
| 0x20-0x80 | Reserved | MUST be set to 0 by senders and ignored by receivers. |

### 5.2 Frame Types

The following frame types are defined in IRP Core v0.1:

| Type Code | Name | Direction | Description |
|-----------|------|-----------|-------------|
| 0x01 | **REQUEST** | C → P | Inference request payload. Body contains the request parameters (model, messages, etc.). |
| 0x02 | **RESPONSE** | P → C | Inference response payload. Body contains generated output. MAY be followed by a RECEIPT frame. |
| 0x03 | **RECEIPT** | P → C | Signed receipt for a completed request. Body contains the receipt data structure. |
| 0x04 | **ERROR** | Both | Protocol error indication. Body contains error code and message. |
| 0x05 | **PING** | Both | Keepalive and latency measurement. Body is empty (length = 0). |
| 0x06 | **PONG** | Both | Response to PING. Body is empty (length = 0). |
| 0x07 | **DISCOVER** | C → P | Capability discovery request. Body contains client-supported versions and capabilities. |
| 0x08 | **DISCOVER_ACK** | P → C | Capability discovery response. Body contains provider capabilities, public key, pricing. |
| 0x09 | **HANDSHAKE** | C → P | Session initiation. Body contains negotiated version, capabilities, QoS class. |
| 0x0A | **HANDSHAKE_ACK** | P → C | Session confirmation. Body contains session ID, confirmed parameters. |
| 0x0B | **GOAWAY** | P → C | Graceful connection termination. Body contains reason code and message. |
| 0x0C-0x1F | Reserved | - | Reserved for future core protocol use. MUST NOT be sent; MUST be treated as error if received. |
| 0x20-0xFF | Extension | Both | Available for extensions. See [Extension Registry](./irp-extensions.md). |

**Direction Legend:**
- C → P: Client to Provider
- P → C: Provider to Client
- Both: Either direction

### 5.3 Body Encoding

All frame bodies with non-zero length MUST be encoded as **length-prefixed JSON**:

1. The body begins with a 4-byte unsigned integer (uint32, big-endian) specifying the length of the JSON payload in bytes.
2. This length prefix is followed by exactly that many bytes of UTF-8 encoded JSON.
3. The total payload length in the frame header equals 4 + json_length.

```
+---------------------------------------------------------------+
|  JSON Length (4 bytes, uint32 BE)  |  JSON Payload (N bytes)  |
+---------------------------------------------------------------+
```

**JSON Requirements:**

- All JSON MUST be valid UTF-8.
- Object keys SHOULD be sorted lexicographically for deterministic canonicalization.
- Numbers MUST be represented without unnecessary precision (no trailing zeros after decimal point unless required).
- The JSON payload MUST NOT exceed 16,777,211 bytes (16 MiB - 4 bytes for the length prefix).
- For empty bodies (e.g., PING, PONG), the payload length in the frame header MUST be 0, and no length prefix or JSON is present.

**Example: REQUEST frame body**

```json
{
  "model": "meta-llama/Llama-3-8B-Instruct",
  "messages": [
    {"role": "user", "content": "Explain quantum computing"}
  ],
  "temperature": 0.7,
  "max_tokens": 512,
  "qos_class": "standard",
  "stream": false
}
```

**Example: RECEIPT frame body**

```json
{
  "cached_tokens": 0,
  "cost_currency": "USD",
  "cost_input": 0.0001,
  "cost_output": 0.0024,
  "cost_total": 0.0025,
  "input_hash": "sha256:abc123...",
  "input_tokens": 42,
  "latency": {
    "queue_ms": 12.5,
    "time_per_output_token_ms": 15.3,
    "time_to_first_token_ms": 145.2,
    "total_ms": 2104.7
  },
  "model": "meta-llama/Llama-3-8B-Instruct",
  "model_version": "3.0.1",
  "output_hash": "sha256:def456...",
  "output_tokens": 128,
  "provider": "together.ai",
  "public_key": "base64:ed25519_pubkey...",
  "reasoning_tokens": 0,
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "signature": "base64:ed25519_sig...",
  "timestamp": "2026-05-08T14:30:00Z",
  "total_tokens": 170
}
```

### 5.4 Transport Mapping

IRP Frames can be carried over multiple transports. This section defines the canonical mappings.

#### 5.4.1 HTTP/1.1 Mapping

Over HTTP/1.1, each inference request/response pair maps to a single HTTP request/response. The frame structure is flattened into HTTP headers and body:

**Request:**

```http
POST /v1/chat/completions HTTP/1.1
Host: api.example.com
Content-Type: application/json
Authorization: Bearer <token>
X-IRP-Request: true
X-IRP-Version: 0.1.0
X-IRP-Capabilities: irp.receipt.v1, irp.qos.standard
X-IRP-Stream-ID: 1

{"model":"...","messages":[...]}
```

**Response:**

```http
HTTP/1.1 200 OK
Content-Type: application/json
X-IRP-Request-ID: 550e8400-e29b-41d4-a716-446655440000
X-IRP-Timestamp: 2026-05-08T14:30:00Z
X-IRP-Provider: together.ai
X-IRP-Model: meta-llama/Llama-3-8B-Instruct
X-IRP-Model-Version: 3.0.1
X-IRP-Input-Tokens: 42
X-IRP-Output-Tokens: 128
X-IRP-Total-Tokens: 170
X-IRP-Cost-Currency: USD
X-IRP-Cost-Input: 0.0001
X-IRP-Cost-Output: 0.0024
X-IRP-Cost-Total: 0.0025
X-IRP-Latency-Total: 2104.7
X-IRP-Latency-TTFT: 145.2
X-IRP-Signature: <base64-encoded-ed25519-signature>
X-IRP-Public-Key: <base64-encoded-ed25519-public-key>

{"choices":[...],"usage":{...}}
```

**HTTP Header Mapping Rules:**

1. The `X-IRP-Request: true` header in the HTTP request signals that the client wants IRP receipt support.
2. The `X-IRP-Version` header specifies the protocol version requested.
3. All receipt fields are transmitted as `X-IRP-*` headers in the HTTP response.
4. Header names are case-insensitive per HTTP specification ([RFC 7230, Section 3.2](https://tools.ietf.org/html/rfc7230#section-3.2)), but this document uses the canonical form `X-IRP-Pascal-Case`. Implementations MAY use any case when parsing or generating headers.
5. Header values MUST be ASCII. Binary data (signatures, public keys) MUST be base64-encoded.
6. Numeric values in headers are represented as decimal strings.
7. Timestamp values use RFC 3339 format.
8. The HTTP response body contains the standard inference response, independent of the IRP headers.

#### 5.4.2 HTTP/2 Mapping

Over HTTP/2, IRP leverages HTTP/2's native framing and multiplexing:

1. Each IRP Stream maps to an HTTP/2 stream. The `stream_id` in the IRP frame header corresponds to the HTTP/2 stream ID.
2. IRP Frames are not wrapped in an additional binary frame layer. Instead, the IRP frame type is indicated by a pseudo-header `:irp-frame-type` or by the HTTP method and path.
3. For inference requests, the standard HTTP/2 request mapping is used, with IRP headers as defined in [Section 5.4.1](#541-http11-mapping).
4. For server-push scenarios (Provider-initiated streams), HTTP/2 server push MAY be used, though this is NOT RECOMMENDED due to limited client support.
5. HTTP/2's flow control and priority mechanisms apply normally.

**HTTP/2 Specific Headers:**

| Pseudo-Header | Value | Description |
|--------------|-------|-------------|
| `:irp-frame-type` | `REQUEST`, `RESPONSE`, `RECEIPT`, `ERROR` | Indicates the IRP frame type for this HTTP/2 stream. |
| `:irp-stream-id` | `<uint32>` | Overrides the HTTP/2 stream ID if the application needs logical stream IDs distinct from transport stream IDs. |

#### 5.4.3 HTTP/3 Mapping

Over HTTP/3 (QUIC), the mapping is identical to HTTP/2, with the following additions:

1. QUIC's connection migration is transparent to IRP.
2. QUIC's 0-RTT MAY be used for inference requests if the Client has previously completed a full handshake with the Provider. Receipts in 0-RTT responses MUST be verified normally.
3. QUIC's datagram extension MAY be used for PING/PONG frames to reduce overhead.

#### 5.4.4 WebSocket Mapping

Over WebSocket, IRP uses its native binary framing:

1. Each WebSocket binary message contains exactly one IRP Frame (header + body).
2. WebSocket text messages MUST NOT be used for IRP Frames.
3. WebSocket ping/pong frames are independent of IRP PING/PONG frames. Both MAY be used.
4. The WebSocket connection is established with a standard HTTP upgrade request. The upgrade request SHOULD include `X-IRP-Version` and `X-IRP-Capabilities` headers.

#### 5.4.5 Direct TCP Mapping

Over direct TCP (without HTTP):

1. IRP Frames are sent directly on the TCP connection, one after another.
2. No additional framing layer is used; the IRP frame header provides length delimitation.
3. The connection begins with a DISCOVER/HANDSHAKE exchange before any inference requests.
4. TCP keepalive SHOULD be enabled. IRP PING/PONG frames MAY also be used.

---

## 6. Procedures

This section defines the exact step-by-step procedures for each phase of the IRP protocol.

### 6.1 Capability Discovery

**Purpose:** Allow the Client to discover Provider capabilities before establishing a session.

**Preconditions:** The Client has the Provider's network address (URL, IP, etc.).

**Procedure:**

1. The Client constructs a DISCOVER frame with the following body:

```json
{
  "client_versions": ["0.1.0"],
  "client_capabilities": ["irp.receipt.v1", "irp.qos.standard"],
  "client_qos_classes": ["realtime", "interactive", "standard"],
  "preferred_transport": "http/2"
}
```

2. The Client sends the DISCOVER frame to the Provider's well-known endpoint:
   - Over HTTP: `GET /.well-known/irp-configuration`
   - Over WebSocket/TCP: Send DISCOVER frame on stream 0

3. The Provider receives the DISCOVER frame and constructs a DISCOVER_ACK response:

```json
{
  "provider_id": "together.ai",
  "supported_versions": ["0.1.0"],
  "selected_version": "0.1.0",
  "supported_capabilities": [
    "irp.receipt.v1",
    "irp.qos.realtime",
    "irp.qos.interactive",
    "irp.qos.standard",
    "irp.qos.batch",
    "irp.qos.background",
    "irp.streaming"
  ],
  "public_key": "base64:MCowBQYDK2VwAyEA...",
  "public_key_algorithm": "Ed25519",
  "public_key_fingerprint": "sha256:abc123...",
  "models": [
    {
      "id": "meta-llama/Llama-3-8B-Instruct",
      "version": "3.0.1",
      "tokenizer": "cl100k_base",
      "context_length": 8192,
      "pricing": {
        "input_per_1m_tokens": 0.10,
        "output_per_1m_tokens": 0.20,
        "currency": "USD"
      }
    }
  ],
  "qos_pricing_multipliers": {
    "realtime": 4.0,
    "interactive": 2.0,
    "standard": 1.0,
    "batch": 0.5,
    "background": 0.25
  },
  "receipt_ttl_seconds": 86400,
  "audit_log_url": "https://audit.together.ai/irp/v0/log",
  "status": "healthy",
  "maintenance_window": null
}
```

4. The Provider sends the DISCOVER_ACK frame to the Client.

5. The Client validates the DISCOVER_ACK:
   - The `selected_version` MUST be in `client_versions`.
   - The `public_key` MUST be a valid base64-encoded Ed25519 public key (32 bytes when decoded).
   - At least one model in `models` MUST match a model the Client intends to use.
   - If `status` is not "healthy", the Client SHOULD delay requests or select an alternative Provider.

6. The Client caches the discovery response. The cache key is the Provider's network address. The cache TTL is the lesser of:
   - The `receipt_ttl_seconds` value from the response
   - 86400 seconds (24 hours)
   - A Client-configured maximum TTL

**Error Handling:**

- If the Provider does not respond within 10 seconds, the Client SHOULD retry up to 3 times with exponential backoff (1s, 2s, 4s).
- If the Provider responds with an ERROR frame or HTTP error status, the Client SHOULD log the error and abort discovery.
- If the Provider's `selected_version` is not supported by the Client, the Client MUST abort and report error 1001 (UNSUPPORTED_VERSION).

### 6.2 Handshake

**Purpose:** Establish a session with negotiated parameters.

**Preconditions:** Discovery has completed successfully.

**When Required:**

- REQUIRED for WebSocket and direct TCP transports.
- OPTIONAL for HTTP/1.1 and HTTP/2 when per-request headers carry all context.
- RECOMMENDED for HTTP when the Client intends to make multiple requests and wants to avoid per-request capability negotiation overhead.

**Procedure:**

1. The Client constructs a HANDSHAKE frame:

```json
{
  "version": "0.1.0",
  "capabilities": ["irp.receipt.v1", "irp.qos.standard"],
  "qos_class": "standard",
  "client_nonce": "base64:random_32_bytes...",
  "client_public_key": "base64:optional_client_ed25519_key...",
  "preferred_compression": null,
  "preferred_encryption": null
}
```

2. The Client sends the HANDSHAKE frame:
   - Over HTTP: `POST /irp/handshake`
   - Over WebSocket/TCP: Send HANDSHAKE frame on stream 0

3. The Provider validates the HANDSHAKE:
   - The `version` MUST be supported.
   - At least one capability in `capabilities` MUST be supported.
   - The `qos_class` MUST be supported.
   - The `client_nonce` MUST be at least 16 bytes when decoded.

4. The Provider constructs a HANDSHAKE_ACK frame:

```json
{
  "session_id": "uuid:session-identifier...",
  "confirmed_version": "0.1.0",
  "confirmed_capabilities": ["irp.receipt.v1", "irp.qos.standard"],
  "confirmed_qos_class": "standard",
  "server_nonce": "base64:random_32_bytes...",
  "session_expiry": "2026-05-08T15:30:00Z",
  "compression": null,
  "encryption": null
}
```

5. The Provider sends the HANDSHAKE_ACK frame to the Client.

6. The Client validates the HANDSHAKE_ACK:
   - The `confirmed_version` MUST match the requested version.
   - The `confirmed_capabilities` MUST be a subset of the requested capabilities.
   - The `confirmed_qos_class` MUST match the requested QoS class (or a fallback that the Client accepts).
   - The `session_expiry` MUST be in the future.

7. The session is now ACTIVE. The Client records the `session_id` and includes it in subsequent requests.

**Session Management:**

- Sessions expire automatically at `session_expiry`.
- Either party MAY terminate a session by sending a GOAWAY frame.
- For HTTP transports without explicit sessions, the session is implicit per connection and expires when the connection closes.

### 6.3 Request Submission

**Purpose:** Submit an inference request and receive a response with a Receipt.

**Preconditions:** Discovery has completed. Handshake has completed (if required).

**Procedure:**

1. The Client constructs a REQUEST frame:

```json
{
  "session_id": "uuid:session-identifier...",
  "request_id": "uuid:request-identifier...",
  "model": "meta-llama/Llama-3-8B-Instruct",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain quantum computing in simple terms."}
  ],
  "temperature": 0.7,
  "max_tokens": 512,
  "top_p": 1.0,
  "qos_class": "standard",
  "stream": false,
  "client_timestamp": "2026-05-08T14:30:00.000Z"
}
```

2. The Client sends the REQUEST frame on a new Client-initiated stream (odd-numbered stream ID).

3. The Provider receives the REQUEST and validates it:
   - The `session_id` MUST correspond to an active session (if sessions are used).
   - The `request_id` MUST be unique within the session. If a duplicate is detected, the Provider MUST respond with error 1002 (DUPLICATE_REQUEST).
   - The `model` MUST be in the set of supported models.
   - The `messages` array MUST not exceed the model's context length.
   - The `qos_class` MUST be supported.

4. The Provider queues and processes the request. During processing, the Provider:
   - Measures queue time (time from receipt to start of processing).
   - Measures time-to-first-token (for streaming) or total generation time.
   - Counts input tokens using the model's tokenizer.
   - Counts output tokens as they are generated.
   - Calculates cost based on token counts and QoS pricing.

5. The Provider constructs a RESPONSE frame containing the inference output:

```json
{
  "request_id": "uuid:request-identifier...",
  "model": "meta-llama/Llama-3-8B-Instruct",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Quantum computing is a type of computing that uses quantum mechanics..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 42,
    "completion_tokens": 128,
    "total_tokens": 170
  }
}
```

6. The Provider constructs a RECEIPT frame containing the signed receipt:

```json
{
  "request_id": "uuid:request-identifier...",
  "timestamp": "2026-05-08T14:30:02.104Z",
  "provider": "together.ai",
  "model": "meta-llama/Llama-3-8B-Instruct",
  "model_version": "3.0.1",
  "input_tokens": 42,
  "output_tokens": 128,
  "reasoning_tokens": 0,
  "cached_tokens": 0,
  "total_tokens": 170,
  "latency": {
    "queue_ms": 12.5,
    "time_to_first_token_ms": 145.2,
    "time_per_output_token_ms": 15.3,
    "total_ms": 2104.7
  },
  "cost_currency": "USD",
  "cost_input": 0.0001,
  "cost_output": 0.0024,
  "cost_total": 0.0025,
  "signature": "base64:ed25519_signature...",
  "public_key": "base64:ed25519_public_key...",
  "input_hash": "sha256:abc123...",
  "output_hash": "sha256:def456..."
}
```

7. The Provider sends the RESPONSE frame followed by the RECEIPT frame on the same stream. The RESPONSE frame MUST have the FIN flag set. The RECEIPT frame MAY be sent as a separate frame or piggybacked on the RESPONSE frame (implementation choice).

8. The Client receives the RESPONSE and RECEIPT frames.

9. For streaming responses, the Provider sends multiple RESPONSE frames (one per chunk) followed by a single RECEIPT frame with the final aggregated counts.

### 6.4 Response with Receipt

**Purpose:** Define the exact behavior for delivering Receipts alongside responses.

**Receipt Delivery Modes:**

IRP supports three modes of Receipt delivery:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Inline** | Receipt fields are included as HTTP headers or fields in the RESPONSE frame body. | HTTP/1.1, simple requests |
| **Separate Frame** | Receipt is delivered in a dedicated RECEIPT frame after the RESPONSE frame. | WebSocket, TCP, HTTP/2 multiplexing |
| **Batch** | Receipts are collected and delivered in a batch at session end or on demand. | High-throughput scenarios, mobile clients |

The delivery mode is negotiated during Handshake via the `irp.receipt.inline`, `irp.receipt.separate`, and `irp.receipt.batch` capabilities. If not negotiated, the default is Inline for HTTP and Separate Frame for WebSocket/TCP.

**Receipt Validation by Client:**

Upon receiving a Receipt, the Client MUST perform the following validation steps:

1. **Signature Verification:**
   - Extract the receipt fields that are part of the signed payload.
   - The signed payload MUST include at minimum: `request_id`, `timestamp`, `provider`, `model`, `input_tokens`, `output_tokens`, `total_tokens`.
   - The signed payload SHOULD include `input_hash` and `output_hash` if present.
   - The signed payload MAY include additional Receipt fields (e.g., `cost_currency`, `cost_input`, `cost_output`, `cost_total`, `latency`, `cached_tokens`, `reasoning_tokens`, `model_version`). Implementations MUST document the exact fields included in the canonicalization scope.
   - Reconstruct the canonical JSON representation: keys sorted lexicographically, no whitespace, compact separators (`,`, `:`).
   - Verify the Ed25519 signature using the Provider's public key obtained during Discovery.
   - If signature verification fails, the Receipt MUST be rejected with status "error".

2. **Token Count Verification:**
   - Count input tokens locally using a tokenizer compatible with the model.
   - Count output tokens locally from the received response text.
   - Compare local counts with Receipt counts.
   - Calculate percentage difference: `abs(server_count - local_count) / server_count * 100`.
   - If the difference exceeds `threshold_percent` (default 5.0%) for either input or output, flag as "warning".

3. **Latency Sanity Check:**
   - Compare reported latency with Client-measured round-trip time.
   - If reported total latency exceeds Client-measured time by more than 50%, flag as "warning".
   - This check is heuristic and MAY be skipped if the Client has high clock skew.

4. **Cost Verification:**
   - Recalculate expected cost: `(input_tokens * input_rate + output_tokens * output_rate) * qos_multiplier`.
   - Compare with Receipt cost. Small rounding differences (< 0.1%) are acceptable.
   - If the difference exceeds 1%, flag as "warning".

5. **Status Determination:**
   - If signature is invalid: status = "error".
   - If any check produces a warning: status = "warning".
   - If all checks pass: status = "valid".

6. **Audit Log Entry:**
   - Record the Receipt, verification results, and status in the Client's local audit log.
   - The audit log entry MUST include the original request ID, timestamp, and status.

### 6.5 Error Handling

**Purpose:** Define consistent error behavior across all transports.

**Error Frame Format:**

An ERROR frame has the following body structure:

```json
{
  "error_code": 1001,
  "error_category": "protocol",
  "error_message": "Unsupported protocol version requested",
  "request_id": "uuid:associated-request...",
  "retryable": false,
  "retry_after_ms": null,
  "details": {}
}
```

**Field Definitions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `error_code` | integer | Yes | The numeric error code. See [Section 7](#7-error-codes). |
| `error_category` | string | Yes | Human-readable category: "protocol", "auth", "quota", "receipt", "server". |
| `error_message` | string | Yes | Human-readable description of the error. |
| `request_id` | string | No | The request ID associated with this error, if applicable. |
| `retryable` | boolean | Yes | Whether the Client SHOULD retry this request. |
| `retry_after_ms` | integer or null | No | Recommended wait time before retry, in milliseconds. |
| `details` | object | No | Additional structured information about the error. |

**HTTP Status Code Mapping:**

When carried over HTTP, IRP errors map to standard HTTP status codes as follows:

| IRP Error Category | HTTP Status Code |
|-------------------|------------------|
| Protocol errors (1000-1999) | 400 Bad Request |
| Authentication errors (2000-2999) | 401 Unauthorized or 403 Forbidden |
| Quota/rate-limit errors (3000-3999) | 429 Too Many Requests |
| Receipt/verification errors (4000-4999) | 400 Bad Request or 422 Unprocessable Entity |
| Server errors (5000-5999) | 500 Internal Server Error or 503 Service Unavailable |

**Error Handling Rules:**

1. When a Provider encounters an error, it MUST send an ERROR frame or an HTTP response with the appropriate status code and `X-IRP-Error-Code` header.

2. The Client MUST handle errors according to the `retryable` flag:
   - If `retryable` is `true`, the Client MAY retry the request after waiting `retry_after_ms` (or using exponential backoff if not specified).
   - If `retryable` is `false`, the Client MUST NOT retry and SHOULD surface the error to the application.

3. For streaming responses, if an error occurs mid-stream, the Provider MUST send an ERROR frame with the FIN flag set and close the stream.

4. The Client MUST be prepared to receive errors at any point: during discovery, handshake, request processing, or response delivery.

### 6.6 Retry Semantics

**Purpose:** Define when and how Clients should retry failed requests.

**Retryable Conditions:**

The following conditions are RECOMMENDED as retryable:

| Condition | Retryable | Backoff Strategy |
|-----------|-----------|------------------|
| Network timeout | Yes | Exponential: 1s, 2s, 4s, max 60s |
| HTTP 503 Service Unavailable | Yes | Exponential with `Retry-After` respect |
| HTTP 429 Too Many Requests | Yes | Respect `Retry-After` header, else exponential |
| IRP error with `retryable: true` | Yes | Use `retry_after_ms` or exponential |
| HTTP 400 Bad Request | No | Do not retry |
| HTTP 401 Unauthorized | No | Do not retry (credentials issue) |
| IRP error with `retryable: false` | No | Do not retry |
| Signature verification failure | No | Do not retry (potential attack) |

**Retry Limits:**

- The Client SHOULD retry a maximum of 3 times for idempotent operations.
- The Client MUST NOT retry non-idempotent operations (e.g., requests with side effects) unless the operation is explicitly designed as idempotent (e.g., using `idempotency-key`).
- Inference requests with the same `request_id` are considered idempotent by the Provider. The Provider SHOULD deduplicate requests with identical `request_id` values within a 5-minute window.

**Exponential Backoff Formula:**

```
delay = min(base_delay * 2^attempt + jitter, max_delay)
```

Where:
- `base_delay` = 1000 milliseconds
- `attempt` = 0-indexed retry attempt (0, 1, 2, ...)
- `jitter` = random value in [0, 1000) milliseconds
- `max_delay` = 60000 milliseconds (60 seconds)

**Idempotency:**

- The Client SHOULD generate a unique `request_id` for every request using UUID v4 or v7.
- The Provider MUST store recent request IDs (minimum 5-minute retention) and return the cached response for duplicate IDs.
- The Provider MUST still generate and sign a fresh Receipt for duplicate requests, with a new timestamp.

---

## 7. Error Codes

IRP defines a comprehensive error code registry with numeric codes grouped by category. Each error code maps to an HTTP status code when carried over HTTP.

### 7.1 Protocol Errors (1000-1999)

Errors related to frame format, version mismatch, and protocol state violations.

| Code | Name | HTTP Status | Description |
|------|------|-------------|-------------|
| 1000 | INVALID_FRAME | 400 | The received frame has an invalid header or body format. |
| 1001 | UNSUPPORTED_VERSION | 400 | The requested protocol version is not supported by the Provider. |
| 1002 | DUPLICATE_REQUEST | 409 | A request with the same `request_id` was already processed. |
| 1003 | INVALID_STREAM_ID | 400 | The stream ID is invalid (e.g., wrong parity, already closed). |
| 1004 | FRAME_TOO_LARGE | 413 | The frame payload exceeds the maximum allowed size (16 MiB). |
| 1005 | INVALID_BODY_ENCODING | 400 | The frame body is not valid length-prefixed JSON. |
| 1006 | MISSING_REQUIRED_FIELD | 400 | A required field is missing from the frame body. |
| 1007 | INVALID_FIELD_VALUE | 400 | A field value is malformed or out of range. |
| 1008 | STREAM_CLOSED | 400 | An operation was attempted on a closed stream. |
| 1009 | PROTOCOL_VIOLATION | 400 | A protocol state machine violation occurred. |
| 1010 | COMPRESSION_ERROR | 400 | Decompression of a compressed frame failed. |
| 1011 | ENCRYPTION_ERROR | 400 | Decryption of an encrypted frame failed. |
| 1012-1099 | Reserved | - | Reserved for future protocol errors. |

### 7.2 Authentication Errors (2000-2999)

Errors related to credential validation, authorization, and identity.

| Code | Name | HTTP Status | Description |
|------|------|-------------|-------------|
| 2000 | AUTH_FAILED | 401 | Authentication failed (invalid or missing credentials). |
| 2001 | AUTH_EXPIRED | 401 | The authentication token or credential has expired. |
| 2002 | INSUFFICIENT_PERMISSIONS | 403 | The authenticated identity lacks permission for the requested operation. |
| 2003 | INVALID_API_KEY | 401 | The API key is malformed or revoked. |
| 2004 | SESSION_EXPIRED | 401 | The session has expired. Re-handshake is required. |
| 2005 | SESSION_INVALID | 401 | The session ID is unknown or has been invalidated. |
| 2006 | RATE_LIMIT_AUTH | 429 | Too many authentication attempts. Try again later. |
| 2007 | PUBLIC_KEY_UNAVAILABLE | 403 | The Provider's public key is not available for verification. |
| 2008 | CLIENT_KEY_REQUIRED | 401 | The Provider requires the Client to present a public key. |
| 2009-2099 | Reserved | - | Reserved for future authentication errors. |

### 7.3 Quota and Rate-Limit Errors (3000-3999)

Errors related to usage limits, quotas, and throttling.

| Code | Name | HTTP Status | Description |
|------|------|-------------|-------------|
| 3000 | QUOTA_EXCEEDED | 429 | The Client has exceeded their usage quota. |
| 3001 | RATE_LIMITED | 429 | The request was rate-limited. See `Retry-After`. |
| 3002 | CONCURRENT_LIMIT_EXCEEDED | 429 | Too many concurrent requests. |
| 3003 | TOKEN_BUDGET_EXCEEDED | 429 | The request would exceed the per-request token budget. |
| 3004 | DAILY_LIMIT_EXCEEDED | 429 | The daily usage limit has been reached. |
| 3005 | MONTHLY_LIMIT_EXCEEDED | 429 | The monthly usage limit has been reached. |
| 3006 | SPEND_LIMIT_EXCEEDED | 429 | The spending limit has been reached. |
| 3007 | MODEL_UNAVAILABLE | 503 | The requested model is temporarily unavailable (quota exhausted on Provider side). |
| 3008 | QOS_UNAVAILABLE | 503 | The requested QoS class is not available at this time. |
| 3009-3099 | Reserved | - | Reserved for future quota errors. |

### 7.4 Receipt and Verification Errors (4000-4999)

Errors related to receipt generation, signature, and verification.

| Code | Name | HTTP Status | Description |
|------|------|-------------|-------------|
| 4000 | RECEIPT_INVALID | 400 | The receipt structure is malformed or missing required fields. |
| 4001 | SIGNATURE_INVALID | 400 | The receipt signature verification failed. |
| 4002 | SIGNATURE_ALGORITHM_UNSUPPORTED | 400 | The signature algorithm is not supported (not Ed25519). |
| 4003 | PUBLIC_KEY_MISMATCH | 400 | The public key in the receipt does not match the discovered public key. |
| 4004 | RECEIPT_EXPIRED | 400 | The receipt timestamp is too old (exceeds `receipt_ttl_seconds`). |
| 4005 | TOKEN_COUNT_MISMATCH | 422 | The token counts in the receipt differ significantly from expected values. |
| 4006 | COST_MISMATCH | 422 | The cost in the receipt does not match the calculated cost. |
| 4007 | LATENCY_MISMATCH | 422 | The reported latency is implausible. |
| 4008 | HASH_MISMATCH | 422 | The content hash in the receipt does not match the actual content. |
| 4009 | RECEIPT_NOT_FOUND | 404 | The requested receipt was not found in the Provider's log. |
| 4010 | AUDIT_LOG_UNAVAILABLE | 503 | The Provider's audit log is temporarily unavailable. |
| 4011-4099 | Reserved | - | Reserved for future receipt errors. |

### 7.5 Server Errors (5000-5999)

Errors indicating internal Provider failures.

| Code | Name | HTTP Status | Description |
|------|------|-------------|-------------|
| 5000 | INTERNAL_ERROR | 500 | An unexpected internal error occurred. |
| 5001 | MODEL_LOAD_ERROR | 503 | The model could not be loaded. |
| 5002 | INFERENCE_ERROR | 500 | An error occurred during inference generation. |
| 5003 | TIMEOUT | 504 | The inference request timed out. |
| 5004 | SIGNING_ERROR | 500 | The Provider failed to sign the receipt. |
| 5005 | STORAGE_ERROR | 500 | The Provider failed to store the receipt in the audit log. |
| 5006 | OVERLOADED | 503 | The Provider is overloaded and cannot accept requests. |
| 5007 | MAINTENANCE | 503 | The Provider is under maintenance. |
| 5008 | DEPENDENCY_ERROR | 502 | A downstream dependency failed. |
| 5009-5099 | Reserved | - | Reserved for future server errors. |

### 7.6 Reserved Ranges

The following code ranges are reserved for future use:

| Range | Purpose |
|-------|---------|
| 0-999 | Never assigned. Codes below 1000 are invalid. |
| 1000-1999 | Protocol errors (core protocol) |
| 2000-2999 | Authentication and authorization errors |
| 3000-3999 | Quota, rate-limit, and resource errors |
| 4000-4999 | Receipt, verification, and audit errors |
| 5000-5999 | Server-side and internal errors |
| 6000-9999 | Reserved for future standardization |
| 10000-19999 | Private use (organization-specific errors) |
| 20000-65535 | Reserved for extensions. See [Extension Registry](./irp-extensions.md). |

**Error Code Registration:**

New error codes in the standard ranges (1000-9999) require specification in an IRP working group document. Codes in the extension range (20000-65535) are self-assigned by extension authors and MUST be documented in the [Extension Registry](./irp-extensions.md).

---

## 8. Versioning

### 8.1 Version Format

IRP uses a three-component version number following Semantic Versioning principles:

```
MAJOR.MINOR.PATCH
```

**Component Definitions:**

| Component | Increment When | Compatibility Guarantee |
|-----------|---------------|------------------------|
| MAJOR | Incompatible wire format or protocol semantics change | No backward compatibility |
| MINOR | New features, new frame types, new capabilities added | Backward compatible for existing features |
| PATCH | Bug fixes, clarifications, documentation updates | Fully backward compatible |

**Version String Rules:**

- Version strings MUST consist of exactly three decimal integers separated by periods.
- Each component MUST be non-negative and fit in a 16-bit unsigned integer (0-65535).
- Version strings MUST NOT contain prefixes (e.g., "v") or suffixes (e.g., "-beta") in the wire format.
- For display purposes, the "v" prefix MAY be used (e.g., "v0.1.0").

**Examples:**

- `0.1.0` — Initial draft release (this document)
- `0.2.0` — Adds streaming receipt support (backward compatible)
- `1.0.0` — First stable release
- `2.0.0` — Wire format change (incompatible with 1.x)

### 8.2 Version Negotiation

**Discovery-Time Negotiation:**

Version negotiation occurs during the Discovery phase:

1. The Client sends a list of supported versions in preference order (most preferred first):

```json
{
  "client_versions": ["0.2.0", "0.1.0"]
}
```

2. The Provider responds with its supported versions and the selected version:

```json
{
  "supported_versions": ["0.1.0"],
  "selected_version": "0.1.0"
}
```

3. The selected version MUST be the highest version supported by both parties.

4. If no common version exists, the Provider MUST respond with error 1001 (UNSUPPORTED_VERSION) and include its supported versions in the error details:

```json
{
  "error_code": 1001,
  "error_message": "No common protocol version",
  "details": {
    "provider_versions": ["0.1.0"],
    "client_versions": ["0.3.0"]
  }
}
```

**Runtime Version Enforcement:**

1. Every frame includes a version byte in the header. The version byte encodes MAJOR and MINOR as nibbles: `(MAJOR << 4) | MINOR`. For version 0.1, the byte is `0x01`.

2. If a Provider receives a frame with an unsupported version byte, it MUST respond with error 1001 (UNSUPPORTED_VERSION).

3. The PATCH component is not encoded in the frame header. Patch-level differences are handled out-of-band (e.g., via the discovery response or documentation).

### 8.3 Deprecation Lifecycle

IRP features and protocol versions follow a four-state lifecycle:

```
+---------------+     +---------------+     +---------------+     +----------+
| Experimental  | --> |    Stable     | --> |  Deprecated   | --> | Removed  |
+---------------+     +---------------+     +---------------+     +----------+
```

**Experimental:**

- New features are introduced as Experimental.
- Experimental features MAY change or be removed without notice.
- Experimental features are identified by capability strings prefixed with `x-` or `experimental.`.
- Implementations SHOULD NOT rely on Experimental features in production.
- Experimental features remain in this state for a minimum of 3 months.

**Stable:**

- After successful community review and implementation experience, an Experimental feature becomes Stable.
- Stable features are guaranteed to remain available for at least 12 months after deprecation.
- Stable features are identified by standard capability strings (no prefix).
- Breaking changes to Stable features require a MAJOR version bump.

**Deprecated:**

- Stable features that are superseded or no longer recommended become Deprecated.
- Deprecated features continue to function but generate warnings.
- The Provider SHOULD include a `Deprecation-Warning` header or field in responses using deprecated features.
- Deprecated features remain available for at least 12 months before removal.

**Removed:**

- After the deprecation period, the feature is Removed.
- Requests using Removed features receive error 1001 (UNSUPPORTED_VERSION) or a feature-specific error.

**Deprecation Timeline Example:**

| Date | Event |
|------|-------|
| 2026-01-01 | Feature X introduced as Experimental |
| 2026-04-01 | Feature X promoted to Stable |
| 2027-04-01 | Feature X marked as Deprecated |
| 2028-04-01 | Feature X Removed |

---

## 9. Security Considerations

### 9.1 Threat Model

IRP is designed to mitigate the following threats, categorized by attacker capability and motivation:

#### 9.1.1 Malicious Provider Over-Billing

**Threat:** A Provider intentionally inflates token counts, applies incorrect pricing, or charges for requests that were not actually processed.

**Impact:** Financial loss for the Client; erosion of trust in the market.

**IRP Mitigation:**
- Receipts are signed by the Provider, creating non-repudiable evidence of the claimed counts.
- Clients verify token counts independently using local tokenizers.
- Discrepancies exceeding the threshold trigger warnings or errors.
- Audit logs (Merkle trees) prevent retroactive modification of receipts.

**Limitation:** A Provider can still over-bill by a small amount (within the verification threshold). The threshold SHOULD be set low enough to deter systematic over-billing but high enough to accommodate legitimate tokenizer differences.

#### 9.1.2 Tampered Receipts

**Threat:** An attacker modifies a Receipt in transit (man-in-the-middle) or a compromised Provider issues fraudulent Receipts.

**Impact:** Incorrect billing; failed verification; audit log corruption.

**IRP Mitigation:**
- All Receipts are signed with Ed25519. Any modification invalidates the signature.
- Clients verify signatures using the Provider's public key obtained during Discovery.
- The Discovery response itself SHOULD be served over HTTPS to prevent MITM substitution of the public key.
- Public key fingerprints allow out-of-band verification.

**Limitation:** If the Provider's private key is compromised, the attacker can forge valid Receipts. Key rotation and monitoring are essential.

#### 9.1.3 Replay Attacks

**Threat:** An attacker replays a valid Receipt to claim duplicate payment or to exhaust quotas.

**Impact:** Duplicate billing; quota exhaustion; audit log pollution.

**IRP Mitigation:**
- Each Receipt contains a unique `request_id` and timestamp.
- Providers deduplicate requests by `request_id` within a time window.
- Audit logs include all Receipts, making replay detection possible during audit.
- Handshake nonces prevent replay of handshake messages.

**Limitation:** A Client that does not verify timestamps or check for duplicate request IDs is vulnerable to replay within the deduplication window.

#### 9.1.4 Timing Side-Channels

**Threat:** An attacker infers sensitive information from the timing of protocol messages (e.g., whether a signature verification succeeded or failed based on response time).

**Impact:** Information leakage; potential for oracle attacks.

**IRP Mitigation:**
- Signature verification by the Client is local and not observable by the Provider.
- Provider-side operations (receipt signing, audit log append) SHOULD be constant-time where feasible.
- Error responses SHOULD NOT reveal internal state through timing differences.

**Limitation:** Complete elimination of timing side-channels is impractical. Defense in depth (rate limiting, monitoring) is recommended.

#### 9.1.5 Denial of Service

**Threat:** An attacker floods the Provider with requests, exhausts resources, or triggers expensive operations.

**Impact:** Service unavailability; degraded performance.

**IRP Mitigation:**
- Rate limiting is enforced at the transport and application layers.
- Receipt signing is computationally lightweight (Ed25519 signing is ~50 microseconds on modern hardware).
- Frame size limits prevent memory exhaustion from malformed frames.
- Connection limits and flow control prevent resource exhaustion.

**Limitation:** A sufficiently resourced attacker can always overwhelm a Provider. IRP does not replace DDoS mitigation infrastructure.

#### 9.1.6 Audit Log Manipulation

**Threat:** A Provider deletes or modifies Receipts in its audit log to hide over-billing.

**Impact:** Dispute resolution failure; regulatory non-compliance.

**IRP Mitigation:**
- The canonical audit log is a Merkle tree, which is tamper-evident.
- The Merkle root is periodically published or submitted to an Auditor.
- Clients can verify inclusion of their Receipts in the Merkle tree.
- The audit log MAY be anchored to a blockchain or public transparency log for additional immutability guarantees.

**Limitation:** A Provider can refuse to append a Receipt to the log. This is detectable (the Client has a signed Receipt that is not in the log) but not preventable.

### 9.2 Mitigations

#### 9.2.1 Transport Security

All IRP communication MUST be encrypted using TLS 1.3 or higher. The following are REQUIRED:

- Certificate validation: Clients MUST validate the Provider's TLS certificate.
- Cipher suites: Only AEAD cipher suites (e.g., TLS_AES_256_GCM_SHA384) SHOULD be used.
- Perfect forward secrecy: Ephemeral key exchange (ECDHE) is REQUIRED.

Direct TCP connections without TLS MUST NOT be used in production. They are permitted only in controlled development/testing environments.

#### 9.2.2 Key Management

Provider Ed25519 signing keys MUST be managed securely:

- Private keys MUST be stored in a hardware security module (HSM) or secure enclave where available.
- Key rotation SHOULD occur at least every 90 days.
- During rotation, the Provider SHOULD support both old and new keys for a grace period of 7 days.
- The Provider MUST publish key rotation events in its discovery response.
- Key fingerprints (SHA-256 of the public key) SHOULD be distributed through multiple channels (DNS, API, documentation).

#### 9.2.3 Input Validation

All protocol inputs MUST be validated:

- Frame headers MUST be checked for valid magic, version, and frame type.
- Payload lengths MUST be checked against the maximum (16 MiB).
- JSON bodies MUST be parsed with strict validation; unknown fields SHOULD be ignored but logged.
- String fields MUST be checked for maximum length to prevent buffer overflows.
- Numeric fields MUST be checked for valid ranges.

#### 9.2.4 Rate Limiting

Providers SHOULD implement multi-layer rate limiting:

- Per-IP rate limiting at the network edge.
- Per-API-key rate limiting at the application layer.
- Per-session rate limiting for persistent connections.
- Global rate limiting to protect against cascading failures.

Rate limit responses MUST include the `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers (or equivalent frame fields).

### 9.3 Cryptographic Requirements

#### 9.3.1 Signature Algorithm

IRP mandates Ed25519 ([RFC 8032](https://tools.ietf.org/html/rfc8032)) for all Receipt signatures.

**Rationale:**
- Ed25519 provides 128-bit security with compact 64-byte signatures.
- Signing and verification are fast (~50us and ~100us respectively on modern CPUs).
- Ed25519 is deterministic, preventing failures due to weak random number generators.
- Ed25519 is widely supported in cryptographic libraries.

**Requirements:**
- Private keys MUST be 32 bytes of cryptographically random data.
- Public keys MUST be 32 bytes.
- Signatures MUST be 64 bytes.
- All keys and signatures transmitted on the wire MUST be base64-encoded.

#### 9.3.2 Hash Algorithm

Content hashing for integrity verification uses SHA-256.

**Requirements:**
- Input and output content MUST be hashed as UTF-8 encoded bytes.
- Hash values in Receipts MUST be prefixed with the algorithm name: `sha256:<hex_digest>`.
- The hex digest MUST be lowercase.

#### 9.3.3 Canonical Serialization

For deterministic signing, Receipt data MUST be serialized using the following canonical JSON rules:

1. Object keys MUST be sorted lexicographically by Unicode code point.
2. No whitespace characters (space, tab, newline, carriage return) are permitted outside string values.
3. Number values MUST use the shortest decimal representation.
4. No trailing commas.
5. Strings MUST be double-quoted.
6. Boolean values MUST be lowercase (`true`, `false`).
7. Null values MUST be lowercase (`null`).

**Example Canonical JSON:**

```json
{"cost_input":0.0001,"cost_output":0.0024,"cost_total":0.0025,"input_tokens":42,"model":"meta-llama/Llama-3-8B-Instruct","output_tokens":128,"provider":"together.ai","request_id":"550e8400-e29b-41d4-a716-446655440000","timestamp":"2026-05-08T14:30:00Z","total_tokens":170}
```

#### 9.3.4 Randomness

All random values (nonces, request IDs, session IDs) MUST be generated using a cryptographically secure random number generator (CSPRNG).

- Nonces MUST be at least 16 bytes.
- Request IDs SHOULD be UUID v4 or v7 (128 bits of randomness).
- Session IDs SHOULD be UUID v4 or v7.

---

## 10. IANA Considerations

This section defines registries that would be created if IRP were submitted to IANA. Until formal registration, these registries are maintained by the IRP Working Group.

### 10.1 HTTP Header Field Registry

The following HTTP header fields are defined for use with IRP:

| Header Field Name | Protocol | Status | Description |
|-------------------|----------|--------|-------------|
| `X-IRP-Request` | http | Standard | Indicates that the client requests IRP receipt support. Value: `true` or `false`. |
| `X-IRP-Version` | http | Standard | The IRP protocol version requested or used. Value: version string (e.g., `0.1.0`). |
| `X-IRP-Capabilities` | http | Standard | Comma-separated list of IRP capabilities requested or supported. |
| `X-IRP-Stream-ID` | http | Standard | The logical stream ID for this request/response. Value: uint32. |
| `X-IRP-Session-ID` | http | Standard | The session identifier established during handshake. Value: UUID string. |
| `X-IRP-Request-ID` | http | Standard | Unique identifier for this request. Value: UUID string. |
| `X-IRP-Timestamp` | http | Standard | Timestamp of receipt generation. Value: RFC 3339. |
| `X-IRP-Provider` | http | Standard | Provider identifier. Value: string. |
| `X-IRP-Model` | http | Standard | Model identifier. Value: string. |
| `X-IRP-Model-Version` | http | Standard | Model version. Value: string. |
| `X-IRP-Input-Tokens` | http | Standard | Number of input tokens. Value: uint32. |
| `X-IRP-Output-Tokens` | http | Standard | Number of output tokens. Value: uint32. |
| `X-IRP-Total-Tokens` | http | Standard | Total token count. Value: uint32. |
| `X-IRP-Cost-Currency` | http | Standard | Currency code for cost. Value: ISO 4217 (e.g., `USD`). |
| `X-IRP-Cost-Input` | http | Standard | Cost for input tokens. Value: decimal. |
| `X-IRP-Cost-Output` | http | Standard | Cost for output tokens. Value: decimal. |
| `X-IRP-Cost-Total` | http | Standard | Total cost. Value: decimal. |
| `X-IRP-Latency-Total` | http | Standard | Total latency in milliseconds. Value: decimal. |
| `X-IRP-Latency-TTFT` | http | Standard | Time to first token in milliseconds. Value: decimal. |
| `X-IRP-Latency-Queue` | http | Standard | Queue time in milliseconds. Value: decimal. |
| `X-IRP-Reasoning-Tokens` | http | Standard | Number of reasoning tokens (e.g., chain-of-thought). Value: uint32. |
| `X-IRP-Cached-Tokens` | http | Standard | Number of cached/prefill tokens. Value: uint32. |
| `X-IRP-Signature` | http | Standard | Ed25519 signature (base64). |
| `X-IRP-Public-Key` | http | Standard | Ed25519 public key (base64). |
| `X-IRP-Error-Code` | http | Standard | IRP error code. Value: uint16. |
| `X-IRP-Error-Category` | http | Standard | Error category. Value: string. |
| `X-IRP-Error-Message` | http | Standard | Human-readable error message. Value: string. |
| `X-IRP-Retryable` | http | Standard | Whether the error is retryable. Value: `true` or `false`. |
| `X-IRP-Retry-After` | http | Standard | Recommended retry delay in milliseconds. Value: uint32. |
| `Deprecation-Warning` | http | Standard | Indicates use of a deprecated feature. Value: feature name and removal date. |

**Registration Template:**

```
Header field name: X-IRP-<Name>
Applicable protocol: http
Status: standard
Author/Change controller: IRP Working Group <irp@example.org>
Specification document(s): This document (IRP Core Protocol)
Related information: [link to companion document if applicable]
```

### 10.2 Frame Type Registry

The following frame types are registered:

| Frame Type Code | Name | Description | Reference |
|-----------------|------|-------------|-----------|
| 0x01 | REQUEST | Inference request | Section 5.2 |
| 0x02 | RESPONSE | Inference response | Section 5.2 |
| 0x03 | RECEIPT | Signed receipt | Section 5.2 |
| 0x04 | ERROR | Protocol error | Section 5.2 |
| 0x05 | PING | Keepalive | Section 5.2 |
| 0x06 | PONG | Keepalive response | Section 5.2 |
| 0x07 | DISCOVER | Capability discovery | Section 5.2 |
| 0x08 | DISCOVER_ACK | Discovery response | Section 5.2 |
| 0x09 | HANDSHAKE | Session initiation | Section 5.2 |
| 0x0A | HANDSHAKE_ACK | Handshake confirmation | Section 5.2 |
| 0x0B | GOAWAY | Graceful termination | Section 5.2 |
| 0x0C-0x1F | Reserved | Reserved for core protocol | Section 5.2 |
| 0x20-0xFF | Extension | Available for extensions | [Extension Registry](./irp-extensions.md) |

**Registration Template:**

```
Frame Type Code: [0x00-0xFF]
Name: [ASCII string]
Description: [Brief description]
Reference: [Document reference]
Contact: [Contact email]
```

### 10.3 Error Code Registry

The following error code ranges are registered:

| Range | Category | Description | Reference |
|-------|----------|-------------|-----------|
| 1000-1999 | Protocol | Frame format, version, state errors | Section 7.1 |
| 2000-2999 | Authentication | Auth, authorization, session errors | Section 7.2 |
| 3000-3999 | Quota | Rate limit, quota, budget errors | Section 7.3 |
| 4000-4999 | Receipt | Receipt validation, signature errors | Section 7.4 |
| 5000-5999 | Server | Internal provider errors | Section 7.5 |
| 6000-9999 | Reserved | Reserved for future standardization | Section 7.6 |
| 10000-19999 | Private Use | Organization-specific errors | Section 7.6 |
| 20000-65535 | Extension | Extension-defined errors | [Extension Registry](./irp-extensions.md) |

**Registration Template:**

```
Error Code: [integer]
Name: [ASCII identifier]
Category: [Protocol|Auth|Quota|Receipt|Server|Extension]
HTTP Status: [HTTP status code]
Description: [Brief description]
Retryable: [true|false]
Reference: [Document reference]
Contact: [Contact email]
```

### 10.4 Capability Identifier Registry

The following capability identifiers are registered:

| Capability Identifier | Status | Description | Reference |
|----------------------|--------|-------------|-----------|
| `irp.receipt.v1` | Standard | Basic signed receipt support | This document |
| `irp.receipt.inline` | Standard | Receipt delivered as HTTP headers | Section 6.4 |
| `irp.receipt.separate` | Standard | Receipt delivered as separate frame | Section 6.4 |
| `irp.receipt.batch` | Standard | Batch receipt delivery | Section 6.4 |
| `irp.streaming` | Standard | Streaming response support | This document |
| `irp.streaming.receipt` | Experimental | Streaming receipt (per-chunk) | [Extension Registry](./irp-extensions.md) |
| `irp.compression.gzip` | Standard | Gzip compression support | This document |
| `irp.compression.zstd` | Standard | Zstd compression support | This document |
| `irp.encryption.tls` | Standard | TLS encryption (always required) | Section 9.2.1 |
| `irp.qos.realtime` | Standard | Realtime QoS class | [QoS Profile](./irp-qos.md) |
| `irp.qos.interactive` | Standard | Interactive QoS class | [QoS Profile](./irp-qos.md) |
| `irp.qos.standard` | Standard | Standard QoS class | [QoS Profile](./irp-qos.md) |
| `irp.qos.batch` | Standard | Batch QoS class | [QoS Profile](./irp-qos.md) |
| `irp.qos.background` | Standard | Background QoS class | [QoS Profile](./irp-qos.md) |
| `irp.auth.apikey` | Standard | API key authentication | [Auth & Discovery Profile](./irp-auth.md) |
| `irp.auth.oauth2` | Standard | OAuth 2.0 authentication | [Auth & Discovery Profile](./irp-auth.md) |
| `irp.auth.mtls` | Standard | Mutual TLS authentication | [Auth & Discovery Profile](./irp-auth.md) |
| `irp.audit.merkle` | Standard | Merkle tree audit log | [Metering & Audit Log](./irp-metering.md) |
| `irp.audit.blockchain` | Experimental | Blockchain-anchored audit log | [Extension Registry](./irp-extensions.md) |

**Capability Identifier Rules:**

- Capability identifiers MUST be ASCII strings.
- Standard capabilities use the prefix `irp.`.
- Experimental capabilities use the prefix `x-irp.` or `experimental.irp.`.
- Vendor-specific capabilities use the prefix `<vendor>.irp.`.
- Capability identifiers MUST NOT exceed 128 characters.

**Registration Template:**

```
Capability Identifier: [string]
Status: [Experimental|Standard|Deprecated]
Description: [Brief description]
Reference: [Document reference]
Contact: [Contact email]
```

### 10.5 QoS Class Identifier Registry

QoS Class identifiers are defined in the [QoS Profile](./irp-qos.md) companion document. The following identifiers are reserved:

| Identifier | Description | Reference |
|-----------|-------------|-----------|
| `realtime` | Sub-100ms latency target | [QoS Profile](./irp-qos.md) |
| `interactive` | Sub-1s latency target | [QoS Profile](./irp-qos.md) |
| `standard` | Sub-10s latency target | [QoS Profile](./irp-qos.md) |
| `batch` | Sub-5min latency target | [QoS Profile](./irp-qos.md) |
| `background` | Sub-1hour latency target | [QoS Profile](./irp-qos.md) |

New QoS class identifiers require specification in the [QoS Profile](./irp-qos.md) or an extension document.

---

## 11. References

### 11.1 Normative References

| Reference | Title | Date |
|-----------|-------|------|
| [RFC 2119](https://tools.ietf.org/html/rfc2119) | Key words for use in RFCs to Indicate Requirement Levels | March 1997 |
| [RFC 8174](https://tools.ietf.org/html/rfc8174) | Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words | May 2017 |
| [RFC 3339](https://tools.ietf.org/html/rfc3339) | Date and Time on the Internet: Timestamps | July 2002 |
| [RFC 6749](https://tools.ietf.org/html/rfc6749) | The OAuth 2.0 Authorization Framework | October 2012 |
| [RFC 8032](https://tools.ietf.org/html/rfc8032) | Edwards-Curve Digital Signature Algorithm (EdDSA) | January 2017 |
| [RFC 8446](https://tools.ietf.org/html/rfc8446) | The Transport Layer Security (TLS) Protocol Version 1.3 | August 2018 |
| [ISO 4217](https://www.iso.org/iso-4217-currency-codes.html) | Codes for the representation of currencies | Current |

### 11.2 Informative References

| Reference | Title | Date |
|-----------|-------|------|
| [RFC 7540](https://tools.ietf.org/html/rfc7540) | Hypertext Transfer Protocol Version 2 (HTTP/2) | May 2015 |
| [RFC 9114](https://tools.ietf.org/html/rfc9114) | HTTP/3 | June 2022 |
| [RFC 9204](https://tools.ietf.org/html/rfc9204) | QPACK: Field Compression for HTTP/3 | June 2022 |
| [MCP](https://modelcontextprotocol.io/) | Model Context Protocol Specification | 2024 |
| [EU AI Act](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689) | Regulation (EU) 2024/1689 (Artificial Intelligence Act) | August 2024 |
| [GB 45438-2025](http://www.gb688.cn/bzgk/gb/newGbInfo?hcno=...) | 人工智能服务计费透明度要求 (AI Service Billing Transparency Requirements) | 2025 |
| [IRP Research](https://github.com/irp-workgroup/research) | IRP Working Group Research Papers | 2026 |
| [SPDY Whitepaper](https://www.chromium.org/spdy/spdy-whitepaper/) | SPDY: An experimental protocol for a faster web | 2009 |
| [QUIC RFC 9000](https://tools.ietf.org/html/rfc9000) | QUIC: A UDP-Based Multiplexed and Secure Transport | May 2021 |

---

## Appendix A: Receipt Verification Algorithm

This appendix provides a normative algorithm for Client-side receipt verification.

### A.1 Input

- `receipt`: The Receipt object received from the Provider.
- `provider_public_key`: The Provider's Ed25519 public key (base64-encoded).
- `local_input_text`: The input text sent to the Provider (optional).
- `local_messages`: OpenAI-format messages sent to the Provider (alternative to `local_input_text`).
- `local_output_text`: The output text received from the Provider.
- `threshold_percent`: The maximum acceptable token count difference (default: 5.0).

### A.2 Algorithm

```
function verify_receipt(receipt, provider_public_key, local_input_text, local_messages, local_output_text, threshold_percent):
    result = new VerificationResult()
    result.request_id = receipt.request_id
    result.threshold_percent = threshold_percent
    result.errors = []

    // Step 1: Signature verification
    signed_data = {
        request_id: receipt.request_id,
        timestamp: receipt.timestamp,
        provider: receipt.provider,
        model: receipt.model,
        input_tokens: receipt.input_tokens,
        output_tokens: receipt.output_tokens,
        total_tokens: receipt.total_tokens
    }
    if receipt.input_hash exists:
        signed_data.input_hash = receipt.input_hash
    if receipt.output_hash exists:
        signed_data.output_hash = receipt.output_hash

    canonical = canonical_json(signed_data)
    result.signature_valid = ed25519_verify(
        public_key = provider_public_key,
        message = canonical,
        signature = receipt.signature
    )

    if not result.signature_valid:
        result.errors.append("Signature verification failed")

    // Step 2: Token count verification
    tokenizer = get_tokenizer(receipt.model)
    if local_messages is not null:
        result.local_input_tokens = tokenizer.count_messages(local_messages)
    else if local_input_text is not null:
        result.local_input_tokens = tokenizer.count(local_input_text)
    else:
        result.local_input_tokens = 0

    if local_output_text is not null:
        result.local_output_tokens = tokenizer.count(local_output_text)
    else:
        result.local_output_tokens = 0
    result.server_input_tokens = receipt.input_tokens
    result.server_output_tokens = receipt.output_tokens

    if receipt.input_tokens > 0:
        result.input_diff = abs(receipt.input_tokens - result.local_input_tokens)
        result.input_diff_percent = (result.input_diff / receipt.input_tokens) * 100

    if receipt.output_tokens > 0:
        result.output_diff = abs(receipt.output_tokens - result.local_output_tokens)
        result.output_diff_percent = (result.output_diff / receipt.output_tokens) * 100

    result.within_threshold = (
        result.input_diff_percent <= threshold_percent AND
        result.output_diff_percent <= threshold_percent
    )

    if not result.within_threshold:
        if result.input_diff_percent > threshold_percent:
            result.errors.append(
                "Input token count differs by " + result.input_diff_percent + "%"
            )
        if result.output_diff_percent > threshold_percent:
            result.errors.append(
                "Output token count differs by " + result.output_diff_percent + "%"
            )

    // Step 3: Determine status
    if not result.signature_valid:
        result.status = "error"
    else if not result.within_threshold:
        result.status = "warning"
    else:
        result.status = "valid"

    result.is_valid = (result.status == "valid")
    return result
```

### A.3 Canonical JSON Function

```
function canonical_json(obj):
    // Sort keys recursively
    if obj is a dictionary:
        sorted_keys = sort(obj.keys())
        entries = []
        for key in sorted_keys:
            entries.append(quote(key) + ":" + canonical_json(obj[key]))
        return "{" + join(entries, ",") + "}"
    else if obj is a list:
        entries = []
        for item in obj:
            entries.append(canonical_json(item))
        return "[" + join(entries, ",") + "]"
    else if obj is a string:
        return json_escape(obj)
    else if obj is a number:
        return serialize_number(obj)
    else if obj is a boolean:
        return obj ? "true" : "false"
    else if obj is null:
        return "null"
```

---

## Appendix B: Example Complete Interaction

This appendix provides a complete example of an IRP interaction over HTTP/1.1.

### B.1 Discovery

**Request:**

```http
GET /.well-known/irp-configuration HTTP/1.1
Host: api.together.ai
Accept: application/json
```

**Response:**

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "provider_id": "together.ai",
  "supported_versions": ["0.1.0"],
  "selected_version": "0.1.0",
  "supported_capabilities": [
    "irp.receipt.v1",
    "irp.qos.standard",
    "irp.qos.interactive"
  ],
  "public_key": "MCowBQYDK2VwAyEA1is1uSqA0x2a0z02r6Dz6qD6qD6qD6qD6qD6qD6qD0=",
  "public_key_algorithm": "Ed25519",
  "models": [
    {
      "id": "meta-llama/Llama-3-8B-Instruct",
      "tokenizer": "cl100k_base",
      "pricing": {
        "input_per_1m_tokens": 0.10,
        "output_per_1m_tokens": 0.20,
        "currency": "USD"
      }
    }
  ],
  "qos_pricing_multipliers": {
    "standard": 1.0,
    "interactive": 2.0
  }
}
```

### B.2 Inference Request with Receipt

**Request:**

```http
POST /v1/chat/completions HTTP/1.1
Host: api.together.ai
Content-Type: application/json
Authorization: Bearer tgp_v1_xxxxxxxxxxxx
X-IRP-Request: true
X-IRP-Version: 0.1.0

{
  "model": "meta-llama/Llama-3-8B-Instruct",
  "messages": [
    {"role": "user", "content": "Hello, world!"}
  ],
  "max_tokens": 100
}
```

**Response:**

```http
HTTP/1.1 200 OK
Content-Type: application/json
X-IRP-Request-ID: 550e8400-e29b-41d4-a716-446655440000
X-IRP-Timestamp: 2026-05-08T14:30:00Z
X-IRP-Provider: together.ai
X-IRP-Model: meta-llama/Llama-3-8B-Instruct
X-IRP-Input-Tokens: 3
X-IRP-Output-Tokens: 15
X-IRP-Total-Tokens: 18
X-IRP-Cost-Currency: USD
X-IRP-Cost-Input: 3.0E-7
X-IRP-Cost-Output: 3.0E-6
X-IRP-Cost-Total: 3.3E-6
X-IRP-Latency-Total: 450.2
X-IRP-Latency-TTFT: 120.5
X-IRP-Signature: MEUCIQDtY7Pj...base64...sig
X-IRP-Public-Key: MCowBQYDK2VwAyEA1is1uSqA0x2a0z02r6Dz6qD6qD6qD6qD6qD6qD6qD0=

{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "model": "meta-llama/Llama-3-8B-Instruct",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I assist you today?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 3,
    "completion_tokens": 15,
    "total_tokens": 18
  }
}
```

### B.3 Client Verification

```python
from irp import ReceiptValidator, create_counter_for_model

# Initialize validator with provider's public key
validator = ReceiptValidator(
    provider_public_key="MCowBQYDK2VwAyEA1is1uSqA0x2a0z02r6Dz6qD6qD6qD6qD6qD6qD6qD0=",
    threshold_percent=5.0
)

# Verify the receipt
result = validator.verify(
    receipt=receipt,
    local_messages=[{"role": "user", "content": "Hello, world!"}],
    local_output_text="Hello! How can I assist you today?"
)

print(result.status)  # "valid", "warning", or "error"
print(result.input_diff_percent)   # e.g., 0.0%
print(result.output_diff_percent)  # e.g., 0.0%
print(result.signature_valid)      # True or False
```

---

## Appendix C: Frame Binary Format Example

This appendix shows the binary representation of a PING frame.

```
Byte offset    Content              Hex value       Description
-----------    -------              ---------       -----------
0-2            Magic                49 52 50        "IRP"
3              Version              01              Version 0.1
4              Frame Type           05              PING
5-8            Stream ID            00 00 00 00     Stream 0 (control)
9-11           Payload Length       00 00 00        0 bytes
12             Flags                00              No flags
```

Total frame size: 13 bytes.

---

## Appendix D: Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0-draft | 2026-05-08 | Initial draft release. Defines core frame format, procedures, error codes, versioning, and security considerations. |

---

*End of Document*
