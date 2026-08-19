# Problem Definition

## Problem Statement
**SOAIDEATHON-S15:** "Digital Twin for Public-Transport Disruptions, Crowd Flow and Emergency Rerouting"

Create a digital twin of a transport network that predicts crowding and service disruption from live or simulated data. Test alternate schedules, communicate rerouting, and quantify impacts before operators act.

## Primary Objective
Build a technically rigorous, scalable, explainable decision-intelligence platform that represents a public transport network as a live digital twin, predicts disruptions, simulates interventions, quantifies consequences, ranks alternatives, and allows operator approval. The system must maintain strict isolation between live state and simulation state, ensuring what-if scenarios never mutate reality.

## Scope
For the initial implementation, the system is optimized for a realistic campus or local bus network. However, the underlying domain model must remain transport-mode agnostic to eventually support other public transport networks (e.g., metro, tram). 

## Central Innovation
**OBSERVE → PREDICT → PROPAGATE → SIMULATE → COMPARE → OPTIMIZE → EXPLAIN → HUMAN APPROVAL → DISPATCH**

The platform must answer:
1. What is happening?
2. What is likely to happen next?
3. How will disruption propagate?
4. What interventions are possible?
5. What will happen under each intervention?
6. Which provides the best outcome?
7. Why is it recommended?
8. What are the measurable trade-offs?
9. Can the operator approve or modify?
