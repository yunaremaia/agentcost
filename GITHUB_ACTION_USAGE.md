## GitHub Action

Add agentcost to your CI workflow:

```yaml
- uses: yunaremaia/agentcost@main
  with:
    path: .
    period: weekly
    output-format: json
```

Alert on cost spikes:

```yaml
- uses: yunaremaia/agentcost@main
  with:
    alert-threshold: "10"
```

### Exit codes

- `0` — all clear
- `1` — cost exceeds threshold or usage detected
