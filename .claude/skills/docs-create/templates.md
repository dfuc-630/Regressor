# Documentation Templates

Quick templates for feature and system documentation.

## Template 1: Feature Documentation (Initial - 00000-init)

### 01-requirements.md (Feature)

```markdown
# Requirements: [Feature Name]

## Summary
[One sentence: what does this feature enable or solve?]

## User Story
As a [user type], I want to [action] so that [benefit].

## Business Requirements

- BR-01: [Requirement]
- BR-02: [Requirement]

## Functional Requirements

- FR-01: [Requirement]
- FR-02: [Requirement]

## Constraints

- [Constraint 1]
- [Constraint 2]

## Performance Targets

- [Performance SLA]
- [Throughput requirement]

## Security / Compliance

- [Security requirement]
- [Compliance rule]
```

### 02-design.md (Feature)

```markdown
# Design: [Feature Name]

## Overview
[Paragraph explaining what this feature does and why]

## Architecture Diagram
[ASCII diagram or description of components]

## Components

### Component 1: [Name]
- Responsibility: [What it does]
- Interface: [Input/output]
- Dependencies: [What it depends on]

### Component 2: [Name]
[Same structure]

## Data Model

### Entity: [Name]
- Field 1: type, constraints
- Field 2: type, constraints

### Relationships
- [Entity A] has many [Entity B]
- [Entity C] belongs to [Entity D]

## Algorithm / Calculation

### [Algorithm Name]
**Input:** [Parameter 1, Parameter 2]
**Output:** [Return value]
**Formula:** [Mathematical formula]
**Example:** [Concrete example with numbers]

## Integration Points

### External Service 1
- Protocol: REST / gRPC / etc.
- Endpoint: [URL or details]
- Authentication: [How authenticated]
- Error handling: [How errors managed]

### Database
- Collection/Table: [Name]
- Indexes: [Indexed fields]

## Error Handling

- **Error 1:** Trigger → Action taken
- **Error 2:** Trigger → Action taken

## Sequence / Flow Diagram
[Visual or ASCII representation of workflow]
```

### 03-plan.md (Feature)

```markdown
# Plan: [Feature Name]

## Overview
[What needs to be built and why]

## Implementation Steps

### Phase 1: Setup & Data Model
- [ ] Design database schema
- [ ] Create migration scripts
- [ ] Validate with team

### Phase 2: Core Feature Implementation
- [ ] Implement [Component 1]
- [ ] Implement [Component 2]
- [ ] Integrate components

### Phase 3: External Integration
- [ ] Connect to [Service 1]
- [ ] Implement error handling
- [ ] Add retry logic

### Phase 4: Testing
- [ ] Unit tests (80% coverage)
- [ ] Integration tests
- [ ] Load tests

### Phase 5: Deployment
- [ ] Code review
- [ ] Merge to main
- [ ] Deploy to staging
- [ ] Deploy to production

## Dependencies

- Service X v2.0+
- Library Y (specific version)
- Database migration: [Reference]

## Success Criteria

- [ ] All code steps completed
- [ ] Tests passing (80%+ coverage)
- [ ] Code reviewed and approved
- [ ] Deployed to production
- [ ] Monitored for 7 days
```

---

## Template 2: System Documentation (Initial - 00000-init)

### 01-requirements.md (System)

```markdown
# Requirements: [System Name]

## Summary
[One sentence: what is this system and its core purpose?]

## System Purpose
[2-3 sentences on why this system exists and what problem it solves]

## Functional Requirements

- FR-01: [System must do X]
- FR-02: [System must do Y]

## Non-Functional Requirements

- Availability: [Target uptime %]
- Latency: [Target response time]
- Throughput: [Requests per second]
- Scalability: [Scaling strategy]

## Constraints

- Infrastructure: [What it runs on]
- Data retention: [How long data kept]
- Compliance: [Standards to follow]

## Dependencies on Other Systems

- System A: [How it integrates]
- System B: [How it integrates]

## Future Considerations

- Planned improvements
- Known limitations
```

### 02-design.md (System)

```markdown
# Design: [System Name]

## Architecture Overview
[High-level description of how the system is organized]

## Architecture Diagram
[Component diagram with data flows]

## Core Components

### [Component 1]
- Role: [What it does]
- Technology: [Tech stack]
- Responsibility: [Specific functions]
- Interfaces: [Exposed APIs]

### [Component 2]
[Same structure]

## Data Flow
[Diagram showing how data moves through components]

## Technology Stack

- Language: [Language and version]
- Framework: [Framework and version]
- Database: [Type and version]
- Message Queue: [If applicable]
- Cache: [If applicable]

## Database Schema
[Entity diagrams, key relationships]

## API Specification
[Endpoints, requests, responses]

## Error Handling & Recovery
- [Failure scenario 1]: Recovery strategy
- [Failure scenario 2]: Recovery strategy

## Monitoring & Observability
- Metrics to track: [Key metrics]
- Logging strategy: [What to log]
- Alerting rules: [When to alert]

## Security Architecture
- Auth mechanism: [How users authenticated]
- Encryption: [What's encrypted and how]
- Access control: [Permissions model]
```

### 03-plan.md (System)

```markdown
# Plan: [System Name]

## Overview
[What is being built/improved and scope]

## Phase 1: Infrastructure Setup
- [ ] Set up environment
- [ ] Configure CI/CD
- [ ] Set up monitoring

## Phase 2: Core Components
- [ ] Implement [Component A]
- [ ] Implement [Component B]
- [ ] Integrate components

## Phase 3: Data Layer
- [ ] Design schema
- [ ] Implement persistence
- [ ] Set up backups

## Phase 4: API Layer
- [ ] Define API spec
- [ ] Implement endpoints
- [ ] Add validation

## Phase 5: Testing & QA
- [ ] Unit tests
- [ ] Integration tests
- [ ] Load testing
- [ ] Security testing

## Phase 6: Deployment
- [ ] High availability setup
- [ ] Deployment automation
- [ ] Monitoring configuration
- [ ] Production deployment

## Success Criteria

- [ ] All components implemented
- [ ] 80%+ test coverage
- [ ] Handles target load without degradation
- [ ] Monitoring alerts configured
- [ ] Team trained on runbooks
- [ ] SLAs established and met
```

---

## Template 3: Incremental Version Update (00001+)

### Structure for Incremental Changes

```markdown
# [Document Type]: [Feature/System Name]

## ⚠️ What Changed from Version [Previous]

- **Added:** [New requirement/component]
- **Modified:** [Changed requirement/behavior]
- **Removed:** [Requirement no longer applies]

## ✅ Unchanged

- All [domain/business logic] remains the same (see version [XX] for details)
- [Other aspects] unchanged

## New Content

[Only the new or changed sections from this point]

---

[Rest of document with updates only]
```

---

## Key Takeaways

- **Version 00000-init:** Complete baseline (all 3 docs)
- **Incremental (00001+):** Only changes + references to previous
- **Requirements:** Max 100 lines, sharp requirements only
- **Plan:** Max 100 lines, checklist format
- **Design:** No limit, absorbs complexity and examples

