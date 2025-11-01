# Metrik Dashboard ve Uyarı Örneği

Bu dosya, yeni eklenen ReAct metriklerini izlemek için örnek bir Prometheus/Grafana dashboard'u ile Elasticsearch tabanlı uyarı senaryosu sunar.

## Prometheus + Grafana Panel Taslağı

```yaml
apiVersion: 1
providers:
  - name: "Aura ReAct"
    orgId: 1
    folder: "Agents"
    type: file
    disableDeletion: true
    options:
      path: dashboards
```

Dashboard JSON taslağı:

```json
{
  "title": "ReAct Agent Sağlığı",
  "panels": [
    {
      "type": "stat",
      "title": "Başarılı Adımlar",
      "targets": [
        {
          "expr": "sum(increase(react_agent_tool_success_total[5m]))"
        }
      ]
    },
    {
      "type": "graph",
      "title": "Adım Süreleri",
      "targets": [
        {
          "expr": "histogram_quantile(0.95, sum(rate(react_agent_step_duration_seconds_sum[5m])) by (tool) / sum(rate(react_agent_step_duration_seconds_count[5m])) by (tool))"
        }
      ]
    }
  ]
}
```

## Elasticsearch (ELK) Uyarı Taslağı

Aşağıdaki Watcher tanımı, başarısız araç kullanımını izleyip Slack'e uyarı göndermek için kullanılabilir.

```json
{
  "trigger": {
    "schedule": {
      "interval": "1m"
    }
  },
  "input": {
    "search": {
      "request": {
        "indices": ["aura-metrics"],
        "body": {
          "query": {
            "range": {
              "@timestamp": {
                "gte": "now-5m"
              }
            }
          },
          "aggs": {
            "by_tool": {
              "terms": {
                "field": "labels.tool.keyword",
                "size": 5
              },
              "aggs": {
                "failures": {
                  "sum": {
                    "field": "values.value"
                  }
                }
              }
            }
          }
        }
      }
    }
  },
  "condition": {
    "script": "return ctx.payload.aggregations.by_tool.buckets.stream().anyMatch(b -> b.failures.value > 0);"
  },
  "actions": {
    "notify_slack": {
      "slack": {
        "account": "alerts",
        "message": {
          "text": "ReAct aracında hata artışı tespit edildi!"
        }
      }
    }
  }
}
```
