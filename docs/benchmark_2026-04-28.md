# Benchmark Report — Sprint 5.5

**Date:** 2026-04-28  
**Input:** walk-in shower / homeiq.io (Florida, Meta, ZIP submit)

## Results

| # | Operation | Model | Score | Cost | Latency | Notes |
|---|---|---|---|---|---|---|
| ✓1 | drafter | `openai/gpt-4o-mini` | 10.0/10 | $0.0028 | 50.2s | ✓ persona_count=4 (valid range 3-5) |
| ✗2 | drafter | `anthropic/claude-3-5-haiku` | FAIL | $0.0000 | 91.7s | ERROR: Exceeded maximum retries (2) for output validation |
| ✗3 | drafter | `meta-llama/llama-3.1-8b-instruct` | FAIL | $0.0000 | 6.7s | ERROR: Invalid response from openai chat completions endpoint: 4 validation errors for ChatCompletion
id
  Input should be a va |
| ✓4 | semantic_extractor | `openai/gpt-4o-mini` | 10.0/10 | $0.0002 | 3.1s | ✓ primary_cta='Click to Get a Price' |
| ✓5 | semantic_extractor | `anthropic/claude-3-haiku` | 10.0/10 | $0.0006 | 1.9s | ✓ primary_cta='Get a Free Price' |
| ✗6 | semantic_extractor | `meta-llama/llama-3.1-8b-instruct` | FAIL | $0.0000 | 1.5s | ERROR: Exceeded maximum retries (1) for output validation |
| ✓7 | pain_point_miner | `openai/gpt-4o-mini` | 10.0/10 | $0.0002 | 2.8s | ✓ 4 pain points (excellent) |
| ✓8 | pain_point_miner | `anthropic/claude-3-haiku` | 9.0/10 | $0.0011 | 3.8s | ✓ 3 pain points (sufficient) |
| ✓9 | hypothesis_generator | `openai/gpt-4o-mini` | 4.0/10 | $0.0001 | 2.9s | ✓ element='headline' |
| ✓10 | hypothesis_generator | `anthropic/claude-3-haiku` | 4.0/10 | $0.0006 | 3.2s | ✓ element='Headline' |

**Total benchmark cost: $0.0056**

## Recommended Model Per Operation

- **drafter**: `openai/gpt-4o-mini` (score=10.0, cost=$0.0028)
- **semantic_extractor**: `openai/gpt-4o-mini` (score=10.0, cost=$0.0002)
- **pain_point_miner**: `openai/gpt-4o-mini` (score=10.0, cost=$0.0002)
- **hypothesis_generator**: `openai/gpt-4o-mini` (score=4.0, cost=$0.0001)

## Quality Detail

### Test 1: drafter / `openai/gpt-4o-mini`
- **Output:** 4 personas | Florida Frank, 68, mobility-challenged retiree
  - ✓ persona_count=4 (valid range 3-5)
  - ✓ decision_helper persona present
  - ✓ JTBD format: 4/4 personas
  - ✓ no platitudes in pain points
  - ✓ realistic income mix: {'30_60k', 'under_30k', '60_100k'}

### Test 2: drafter / `anthropic/claude-3-5-haiku`
- **Output:** 
  - ERROR: Exceeded maximum retries (2) for output validation

### Test 3: drafter / `meta-llama/llama-3.1-8b-instruct`
- **Output:** 
  - ERROR: Invalid response from openai chat completions endpoint: 4 validation errors for ChatCompletion
id
  Input should be a va

### Test 4: semantic_extractor / `openai/gpt-4o-mini`
- **Output:** cta='Click to Get a Price' | conf=0.95
  - ✓ primary_cta='Click to Get a Price'
  - ✓ hero_headline='No More Long Shower Renovations… Try This Instead....'
  - ✓ 4 trust signals found
  - ✓ confidence=0.95
  - ✓ 3 key benefits identified

### Test 5: semantic_extractor / `anthropic/claude-3-haiku`
- **Output:** cta='Get a Free Price' | conf=0.90
  - ✓ primary_cta='Get a Free Price'
  - ✓ hero_headline='No More Long Shower Renovations… Try This Instead....'
  - ✓ 3 trust signals found
  - ✓ confidence=0.90
  - ✓ 3 key benefits identified

### Test 6: semantic_extractor / `meta-llama/llama-3.1-8b-instruct`
- **Output:** 
  - ERROR: Exceeded maximum retries (1) for output validation

### Test 7: pain_point_miner / `openai/gpt-4o-mini`
- **Output:** 4 pain points | urgency=high
  - ✓ 4 pain points (excellent)
  - ✓ no platitudes in pain points
  - ✓ trigger phrases: 4/4 pain points
  - ✓ urgency_level=high (correct for safety niche)

### Test 8: pain_point_miner / `anthropic/claude-3-haiku`
- **Output:** 3 pain points | urgency=high
  - ✓ 3 pain points (sufficient)
  - ✓ no platitudes in pain points
  - ✓ trigger phrases: 3/3 pain points
  - ✓ urgency_level=high (correct for safety niche)

### Test 9: hypothesis_generator / `openai/gpt-4o-mini`
- **Output:** element='headline' | risk=low
  - ✓ element='headline'
  - ✓ variant differs from control
  - ✓ primary_metric='ZIP submit rate'
  - ✓ risk_level='low'
  - ℹ️  hypothesis scorer: add your criteria for 6 more points

### Test 10: hypothesis_generator / `anthropic/claude-3-haiku`
- **Output:** element='Headline' | risk=medium
  - ✓ element='Headline'
  - ✓ variant differs from control
  - ✓ primary_metric='ZIP code submit rate'
  - ✓ risk_level='medium'
  - ℹ️  hypothesis scorer: add your criteria for 6 more points
