---
description: "Arco ecosystem from Integrator's perspective: brands, legacy/modern systems, sources of truth. USE when the user mentions Arco brand names (SAS, SAE, IS, NSE), discusses legacy vs modern Arco systems, asks about which service owns a piece of data, or debugs anything spanning the Arco ecosystem."
user-invocable: false
---

# Arco Architecture

Arco ecosystem as seen from Integrator. This skill grows incrementally during debug sessions.

---

## Brands

- **SAS** (Sistema Ari de Sa)
- **SAE** (Sistema de Apoio ao Ensino)
- **IS** (International School)
- **NSE** (sub-brands under NSE umbrella)

Details on sub-brands and brand-to-system mappings will be filled as we discover them.

---

## Legacy 1.0 Systems

| System | Description |
|--------|-------------|
| Protheus SAS | ERP for SAS brand |
| Protheus SAE | ERP for SAE brand |
| Protheus IS | ERP for IS brand |
| SAP1 | Legacy SAP instance |
| B2C Store | Legacy e-commerce (B2C) |
| B2B Store | Legacy e-commerce (B2B) |

---

## Modern 2.0 Systems

| System | Description |
|--------|-------------|
| CRM (Salesforce) | Customer relationship management |
| OMS (Salesforce) | Order management system |
| SAP4 | Modern SAP instance |
| WMS (Oracle) | Warehouse management |
| TMS | Transportation management |
| Meu Arco B2C | Modern B2C platform |
| Meu Arco B2B | Modern B2B platform |
| Configurador (Salesforce) | Product configurator |
| 4MDG | Master Data Governance SaaS -- product data management, registration centers, data quality |

---

## Sources of Truth

| Domain | Source |
|--------|--------|
| Schools | CRM (Salesforce) |
| Products | 4MDG |
| RF / Parents | CRM (Salesforce) |
| Sales Agreements | Legacy ERPs (Protheus SAS/SAE/IS) |

---

## Order & Invoice Flows (per brand)

**SAS:**
```
SAS Stores 1.0 (+ Isaac as exception) -order-> Integrator -> OMS -invoice-> Integrator -> Protheus SAS (ERP 1.0)
```
Integrator handles both order ingestion and invoice delivery for SAS.

**NSE:**
```
Meu Arco B2B 2.0 -order-> OMS (direct, no Integrator)
OMS -invoice-> Integrator -> SAP1 (ERP 1.0)
```
Integrator handles only the invoice leg for NSE.

**SAE:**
```
OMS -> SAP4 (direct, no Integrator involvement)
```

**General rule:** Integrator sits in the order path only for 1.0 stores (+ Isaac as exception). 2.0 stores talk to OMS directly.

*More flows will be added as we discover them.*

---

## Integrator's Role

- **Anti-corruption layer** between 1.0 and 2.0 systems
- **Strangler-fig facade** -- gradually replaces legacy integrations as 2.0 systems mature
- Normalizes data formats, translates between system-specific schemas
- Handles **order ingestion** from 1.0 stores (+ Isaac) to OMS
- Handles **invoice delivery** from OMS to legacy ERPs (SAS -> Protheus SAS, NSE -> SAP1)
- Grows incrementally as more flows migrate from 1.0 to 2.0
